# 생성: 2026-10-29 23:25 KST
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
    assert service.load_roster(easy(), 3) == "승인: 명단을 올림(학생 8명, 팀 3개)"
    state = service.get_state()
    assert state.teams == {1: [], 2: [], 3: []}
    assert len(state.unassigned) == 8
    assert state.closed is False


def test_load_roster_keeps_admin():
    service.ensure_admin("pw1")
    service.load_roster(easy(), 3)
    service.load_roster(easy(), 4)
    assert service.login("admin", "pw1") is not None
    assert len(service.get_state().teams) == 4


def test_student_password_hashed():
    service.load_roster(easy(), 3)
    with get_pool().connection() as conn:
        h = conn.execute("select password_hash from tf_students where student_no = '2026101'").fetchone()[0]
    assert h != "1234" and h.startswith("$2")
    assert service.login("2026101", "1234") is not None
    assert service.login("2026101", "0000") is None


def test_login_strips_spaces():
    service.load_roster(easy(), 3)
    assert service.login(" 2026101 ", "1234") is not None
