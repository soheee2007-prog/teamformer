# 생성: 2026-10-29 23:31 KST
# 앱의 동작(로그인, 명단, 지원, 투표, 마감, 확정)을 DB 트랜잭션으로 처리하고 안내 문구를 돌려준다.
# 안내 문구는 "승인", "대기", "거절", "막힘" 가운데 하나로 시작한다(공고 2.7절).
from dataclasses import dataclass

import bcrypt
from psycopg.errors import UniqueViolation

from db import get_pool
from rules import Student, apply_block_reason, check_assignment

STUDENT_PASSWORD = b"1234"
ADMIN_ONLY = "막힘: 관리자만 할 수 있음"


@dataclass
class User:
    id: int
    student_no: str
    name: str
    is_admin: bool


@dataclass
class Pending:
    application_id: int
    team_no: int
    applicant: Student
    votes: dict[str, str]  # 투표자 학번 -> "찬성" 또는 "거부"


@dataclass
class State:
    closed: bool
    teams: dict[int, list[Student]]
    team_names: dict[int, str]
    unassigned: list[Student]
    pending: list[Pending]
    my_pending_team: int | None


def _hash(pw: bytes) -> str:
    return bcrypt.hashpw(pw, bcrypt.gensalt(rounds=10)).decode()


def ensure_admin(password: str) -> None:
    """관리자 계정을 만들거나 비밀번호를 ADMIN_PASSWORD 로 맞춘다(공고 2.1절)."""
    with get_pool().connection() as conn:
        row = conn.execute("select id, password_hash from tf_students where student_no = 'admin'").fetchone()
        if row is None:
            conn.execute(
                "insert into tf_students (student_no, name, main_role, password_hash, is_admin) "
                "values ('admin', '관리자', '관리자', %s, true)",
                (_hash(password.encode()),),
            )
        elif not bcrypt.checkpw(password.encode(), row[1].encode()):
            conn.execute("update tf_students set password_hash = %s where id = %s", (_hash(password.encode()), row[0]))


def login(student_no: str, password: str) -> User | None:
    with get_pool().connection() as conn:
        row = conn.execute(
            "select id, student_no, name, is_admin, password_hash from tf_students where student_no = %s",
            (student_no.strip(),),
        ).fetchone()
    if row is None or not bcrypt.checkpw(password.encode(), row[4].encode()):
        return None
    return User(row[0], row[1], row[2], row[3])


def _is_admin(conn, student_no: str) -> bool:
    row = conn.execute("select is_admin from tf_students where student_no = %s", (student_no,)).fetchone()
    return bool(row and row[0])


def load_roster(by: str, students: list[Student], team_count: int) -> str:
    """관리자 계정만 남기고 모두 지운 뒤 명단과 빈 팀을 만든다(공고 2.6절). by: 실행한 사람의 학번."""
    with get_pool().connection() as conn:
        if not _is_admin(conn, by):
            return ADMIN_ONLY
    hashes = [_hash(STUDENT_PASSWORD) for _ in students]
    with get_pool().connection() as conn, conn.transaction():
        conn.execute("delete from tf_applications")
        conn.execute("delete from tf_members")
        conn.execute("delete from tf_teams")
        conn.execute("delete from tf_students where not is_admin")
        conn.execute("delete from tf_settings")
        for s, h in zip(students, hashes):
            sid = conn.execute(
                "insert into tf_students (student_no, name, main_role, password_hash) values (%s, %s, %s, %s) returning id",
                (s.student_no, s.name, s.main_role, h),
            ).fetchone()[0]
            for role in s.sub_roles:
                conn.execute("insert into tf_student_sub_roles (student_id, role) values (%s, %s)", (sid, role))
        for n in range(1, team_count + 1):
            conn.execute("insert into tf_teams (team_no, name) values (%s, %s)", (n, f"팀{n}"))
    return f"승인: 명단을 올림(학생 {len(students)}명, 팀 {team_count}개)"


def _students(conn) -> dict[int, Student]:
    """학생 id -> Student (관리자 제외)."""
    subs: dict[int, list[str]] = {}
    for sid, role in conn.execute("select student_id, role from tf_student_sub_roles order by role"):
        subs.setdefault(sid, []).append(role)
    rows = conn.execute("select id, student_no, name, main_role from tf_students where not is_admin order by student_no")
    return {r[0]: Student(r[1], r[2], r[3], tuple(subs.get(r[0], []))) for r in rows}


def get_state(student_no: str | None = None) -> State:
    with get_pool().connection() as conn:
        return _read_state(conn, student_no)


def _read_state(conn, student_no: str | None) -> State:
    # get_state 와 confirm 이 같은 연결(트랜잭션)로 읽도록 나눔
    students = _students(conn)
    closed = conn.execute("select 1 from tf_settings where key = 'closed'").fetchone() is not None
    teams_rows = conn.execute("select id, team_no, name from tf_teams order by team_no").fetchall()
    team_no_of = {r[0]: r[1] for r in teams_rows}
    teams = {r[1]: [] for r in teams_rows}
    names = {r[1]: r[2] for r in teams_rows}
    members = set()
    for team_id, sid in conn.execute("select team_id, student_id from tf_members order by team_id, slot_no"):
        teams[team_no_of[team_id]].append(students[sid])
        members.add(sid)
    votes: dict[int, dict[str, str]] = {}
    for app_id, voter_id, vote in conn.execute(
        "select v.application_id, v.voter_id, v.vote from tf_votes v "
        "join tf_applications a on a.id = v.application_id where a.status = '대기'"
    ):
        votes.setdefault(app_id, {})[students[voter_id].student_no] = vote
    pending = [
        Pending(app_id, team_no_of[team_id], students[sid], votes.get(app_id, {}))
        for app_id, team_id, sid in conn.execute(
            "select id, team_id, student_id from tf_applications where status = '대기' order by created_at, id"
        )
    ]
    unassigned = [s for sid, s in students.items() if sid not in members]
    mine = next((p.team_no for p in pending if p.applicant.student_no == student_no), None)
    return State(closed, teams, names, unassigned, pending, mine)


def log_ai(model: str, outcome: str, detail: str, seconds: float) -> None:
    with get_pool().connection() as conn:
        conn.execute(
            "insert into tf_ai_logs (model, outcome, detail, seconds) values (%s, %s, %s, %s)",
            (model, outcome, detail[:1000], seconds),
        )


# ---- 지원, 투표, 마감, 확정 ----

def _closed(conn) -> bool:
    return conn.execute("select 1 from tf_settings where key = 'closed'").fetchone() is not None


def _student(conn, student_no: str) -> tuple[int, Student] | None:
    row = conn.execute("select id from tf_students where student_no = %s and not is_admin", (student_no,)).fetchone()
    if row is None:
        return None
    return row[0], _students(conn)[row[0]]


def _members(conn, team_id: int) -> list[tuple[int, Student]]:
    students = _students(conn)
    rows = conn.execute("select student_id from tf_members where team_id = %s order by slot_no", (team_id,))
    return [(sid, students[sid]) for (sid,) in rows]


def _add_member(conn, team_id: int, student_id: int) -> None:
    used = {r[0] for r in conn.execute("select slot_no from tf_members where team_id = %s", (team_id,))}
    slot = min(n for n in range(1, 5) if n not in used)
    conn.execute("insert into tf_members (team_id, slot_no, student_id) values (%s, %s, %s)", (team_id, slot, student_id))


def apply(student_no: str, team_no: int) -> str:
    """팀에 지원한다(PRD 4.2절). 막히면 DB에 기록하지 않는다."""
    try:
        with get_pool().connection() as conn, conn.transaction():
            if _closed(conn):
                return "막힘: 모집이 마감됨"
            found = _student(conn, student_no)
            if found is None:
                return "막힘: 학생을 찾을 수 없음"
            sid, s = found
            # 같은 팀에 대한 지원, 투표가 동시에 처리되지 않도록 팀 행을 잠근다
            team = conn.execute("select id from tf_teams where team_no = %s for update", (team_no,)).fetchone()
            if team is None:
                return "막힘: 없는 팀"
            team_id = team[0]
            if conn.execute("select 1 from tf_members where student_id = %s", (sid,)).fetchone():
                return "막힘: 이미 팀이 있음"
            if conn.execute("select 1 from tf_applications where student_id = %s and status = '대기'", (sid,)).fetchone():
                return "막힘: 결과를 기다리는 지원이 있음"
            members = [m for _, m in _members(conn, team_id)]
            reason = apply_block_reason(members, s)
            if reason:
                return f"막힘: {reason}"
            if not members:
                _add_member(conn, team_id, sid)
                conn.execute(
                    "insert into tf_applications (team_id, student_id, status, reason, decided_at) "
                    "values (%s, %s, '승인', '빈 팀', now())",
                    (team_id, sid),
                )
                return f"승인: 팀{team_no}에 들어감"
            conn.execute("insert into tf_applications (team_id, student_id, status) values (%s, %s, '대기')", (team_id, sid))
            return f"대기: 팀{team_no} 팀원의 투표를 기다림"
    except UniqueViolation:
        return "막힘: 다른 학생이 먼저 들어감"


def vote(voter_no: str, applicant_no: str, yes: bool) -> str:
    """내 팀에 들어온 지원에 찬성 또는 거부한다(PRD 4.3절)."""
    try:
        with get_pool().connection() as conn, conn.transaction():
            if _closed(conn):
                return "막힘: 모집이 마감됨"
            voter = _student(conn, voter_no)
            applicant = _student(conn, applicant_no)
            if voter is None or applicant is None:
                return "막힘: 학생을 찾을 수 없음"
            vid, aid = voter[0], applicant[0]
            row = conn.execute("select team_id from tf_members where student_id = %s", (vid,)).fetchone()
            if row is None:
                return "막힘: 이 지원에 투표할 수 없음"
            team_id = row[0]
            team_no = conn.execute("select team_no from tf_teams where id = %s for update", (team_id,)).fetchone()[0]
            app = conn.execute(
                "select id from tf_applications where student_id = %s and team_id = %s and status = '대기'",
                (aid, team_id),
            ).fetchone()
            if app is None:
                return "막힘: 이 지원에 투표할 수 없음"
            app_id = app[0]
            if conn.execute("select 1 from tf_votes where application_id = %s and voter_id = %s", (app_id, vid)).fetchone():
                return "막힘: 이미 투표함"
            conn.execute(
                "insert into tf_votes (application_id, voter_id, vote) values (%s, %s, %s)",
                (app_id, vid, "찬성" if yes else "거부"),
            )
            if not yes:
                _decide(conn, app_id, "거절", "팀원이 거부함")
                return "거절: 팀원이 거부함"
            members = _members(conn, team_id)
            agreed = {r[0] for r in conn.execute(
                "select voter_id from tf_votes where application_id = %s and vote = '찬성'", (app_id,))}
            if not all(m_id in agreed for m_id, _ in members):
                return "대기: 다른 팀원의 투표를 기다림"
            # 승인 직전 재검사: 앞의 지원이 먼저 승인되어 팀이 바뀌었을 수 있다
            reason = apply_block_reason([m for _, m in members], applicant[1])
            if reason:
                _decide(conn, app_id, "거절", reason)
                return f"거절: {reason}"
            _add_member(conn, team_id, aid)
            _decide(conn, app_id, "승인", "팀원 모두 찬성")
            return f"승인: {applicant[1].name}이(가) 팀{team_no}에 들어감"
    except UniqueViolation:
        return "막힘: 다른 학생이 먼저 들어감"


def _decide(conn, app_id: int, status: str, reason: str) -> None:
    conn.execute(
        "update tf_applications set status = %s, reason = %s, decided_at = now() where id = %s",
        (status, reason, app_id),
    )


def close(by: str) -> str:
    """모집 마감: 대기 지원을 거절하고, 혼자인 팀의 학생을 팀에서 뺀다(PRD 4.4절)."""
    with get_pool().connection() as conn, conn.transaction():
        if not _is_admin(conn, by):
            return ADMIN_ONLY
        if _closed(conn):
            return "막힘: 이미 마감함"
        conn.execute("insert into tf_settings (key, value) values ('closed', 'true')")
        rejected = conn.execute(
            "update tf_applications set status = '거절', reason = '모집 마감', decided_at = now() where status = '대기'"
        ).rowcount
        removed = conn.execute(
            "delete from tf_members where team_id in "
            "(select team_id from tf_members group by team_id having count(*) = 1)"
        ).rowcount
    return f"승인: 모집을 마감함(대기 지원 {rejected}건 거절, 혼자인 학생 {removed}명 팀에서 빠짐)"


def confirm(by: str, assignment: list[tuple[str, int]]) -> str:
    """배정안을 지금 DB 상태로 다시 검사한 뒤 저장한다(PRD 4.7절)."""
    try:
        with get_pool().connection() as conn, conn.transaction():
            if not _is_admin(conn, by):
                return ADMIN_ONLY
            conn.execute("select id from tf_teams order by id for update")
            if not _closed(conn):
                return "막힘: 모집을 마감하지 않음"
            state = _read_state(conn, None)
            errors = check_assignment(state.teams, state.unassigned, assignment)
            if errors:
                return f"막힘: 배정안이 지금 상태와 맞지 않음({errors[0]})"
            team_ids = {r[1]: r[0] for r in conn.execute("select id, team_no from tf_teams")}
            ids = {r[1]: r[0] for r in conn.execute("select id, student_no from tf_students")}
            for no, team_no in assignment:
                _add_member(conn, team_ids[team_no], ids[no])
        return f"승인: 배정안을 확정함({len(assignment)}명)"
    except UniqueViolation:
        return "막힘: 다른 학생이 먼저 들어감"
