# 생성: 2026-10-29 23:25 KST
# 앱의 동작(로그인, 명단, 지원, 투표, 마감, 확정)을 DB 트랜잭션으로 처리하고 안내 문구를 돌려준다.
# 안내 문구는 "승인", "대기", "거절", "막힘" 가운데 하나로 시작한다(공고 2.7절).
from dataclasses import dataclass

import bcrypt

from db import get_pool
from rules import Student

STUDENT_PASSWORD = b"1234"


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


def load_roster(students: list[Student], team_count: int) -> str:
    """관리자 계정만 남기고 모두 지운 뒤 명단과 빈 팀을 만든다(공고 2.6절)."""
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
