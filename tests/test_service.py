# 생성: 2026-10-29 23:30 KST
# service.py 시험. 실제 Supabase를 쓰므로 앱 데이터가 초기화된다.
from pathlib import Path

import service
from db import get_pool
from roster import parse_roster

DATA = Path(__file__).parent / "data"


def easy():
    return parse_roster((DATA / "쉬움.csv").read_bytes())


# ---- 과제 5: 계정, 명단, 상태 ----

def test_ensure_admin_and_login():
    service.ensure_admin("pw1")
    user = service.login("admin", "pw1")
    assert user is not None and user.is_admin
    assert service.login("admin", "x") is None


def test_ensure_admin_updates_password():
    service.ensure_admin("pw1")
    service.ensure_admin("pw2")
    assert service.login("admin", "pw1") is None
    assert service.login("admin", "pw2") is not None


def test_load_roster():
    assert service.load_roster("admin", easy(), 3) == "승인: 명단을 올림(학생 8명, 팀 3개)"
    state = service.get_state()
    assert state.teams == {1: [], 2: [], 3: []}
    assert len(state.unassigned) == 8
    assert state.closed is False


def test_load_roster_keeps_admin():
    service.ensure_admin("pw1")
    service.load_roster("admin", easy(), 3)
    service.load_roster("admin", easy(), 4)
    assert service.login("admin", "pw1") is not None
    assert len(service.get_state().teams) == 4


def test_student_password_hashed():
    service.load_roster("admin", easy(), 3)
    with get_pool().connection() as conn:
        h = conn.execute("select password_hash from tf_students where student_no = '2026101'").fetchone()[0]
    assert h != "1234" and h.startswith("$2")
    assert service.login("2026101", "1234") is not None
    assert service.login("2026101", "0000") is None


def test_login_strips_spaces():
    service.load_roster("admin", easy(), 3)
    assert service.login(" 2026101 ", "1234") is not None


# ---- 과제 6: 지원, 투표, 마감, 확정 ----
from rules import solve  # noqa: E402


def test_new_member_must_vote():
    service.load_roster("admin", easy(), 3)
    assert service.apply("2026101", 1).startswith("승인")
    assert service.apply("2026104", 1).startswith("대기")
    assert service.apply("2026108", 1).startswith("대기")
    assert service.vote("2026101", "2026108", True).startswith("승인")
    # 2026108 이 새 팀원이 되었으므로 2026104 의 지원에도 투표해야 한다
    assert service.vote("2026101", "2026104", True).startswith("대기")
    assert service.vote("2026108", "2026104", True).startswith("승인")


def test_vote_twice_blocked():
    service.load_roster("admin", easy(), 3)
    service.apply("2026101", 1)
    service.apply("2026108", 1)
    service.vote("2026101", "2026108", True)
    service.apply("2026104", 1)
    assert service.vote("2026101", "2026104", True).startswith("대기")
    assert service.vote("2026101", "2026104", True) == "막힘: 이미 투표함"


def test_non_member_cannot_vote():
    service.load_roster("admin", easy(), 3)
    service.apply("2026101", 1)
    service.apply("2026104", 1)
    assert service.vote("2026102", "2026104", True) == "막힘: 이 지원에 투표할 수 없음"


def test_apply_after_close():
    service.load_roster("admin", easy(), 3)
    assert service.close("admin").startswith("승인")
    assert service.apply("2026101", 1) == "막힘: 모집이 마감됨"


def test_close_twice():
    service.load_roster("admin", easy(), 3)
    service.close("admin")
    assert service.close("admin") == "막힘: 이미 마감함"


def test_confirm_rechecks():
    service.load_roster("admin", easy(), 3)
    for no, team in [("2026101", 1), ("2026102", 2), ("2026103", 3)]:
        service.apply(no, team)
    service.close("admin")
    state = service.get_state()
    plan = solve(state.teams, state.unassigned)
    service.load_roster("admin", easy(), 3)
    assert service.confirm("admin", plan).startswith("막힘")
    assert all(ms == [] for ms in service.get_state().teams.values())


# ---- 최종 검토 뒤 고침 ----

def test_admin_functions_require_admin():
    service.load_roster("admin", easy(), 3)
    assert service.load_roster("2026101", easy(), 3) == "막힘: 관리자만 할 수 있음"
    assert service.close("2026101") == "막힘: 관리자만 할 수 있음"
    assert service.confirm("2026101", []) == "막힘: 관리자만 할 수 있음"
