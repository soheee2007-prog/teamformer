# 생성: 2026-10-29 23:36 KST
# 화면 시험(streamlit.testing.v1.AppTest). 자동 채점 프로그램이 찾는 key가 있는지 확인한다(공고 2.7절).
# 실제 Supabase를 쓴다.
import re
from pathlib import Path

from streamlit.testing.v1 import AppTest

import service
from config import get_secret
from roster import parse_roster

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "tests" / "data"


def start() -> AppTest:
    at = AppTest.from_file(str(ROOT / "streamlit_app.py"), default_timeout=60)
    return at.run()


def log_in(at: AppTest, no: str, pw: str) -> AppTest:
    at.text_input(key="login_student_no").input(no)
    at.text_input(key="login_password").input(pw)
    at.button(key="login_submit").click()
    return at.run()


def texts(at: AppTest) -> list[str]:
    return [m.value for m in at.markdown] + [m.value for m in at.caption]


def keys(at: AppTest) -> set[str]:
    return {b.key for b in at.button}


def test_login_keys():
    at = start()
    assert at.text_input(key="login_student_no") is not None
    assert at.text_input(key="login_password") is not None
    assert "login_submit" in keys(at)


def test_admin_view_keys():
    at = log_in(start(), "admin", get_secret("ADMIN_PASSWORD"))
    assert {"admin_start", "admin_close", "admin_assign", "admin_confirm"} <= keys(at)
    assert at.number_input(key="admin_team_count") is not None


def test_student_view_keys():
    service.load_roster(parse_roster((DATA / "쉬움.csv").read_bytes()), 3)
    at = log_in(start(), "2026101", "1234")
    assert {"apply_1", "apply_2", "apply_3"} <= keys(at)
    at.button(key="apply_1").click()
    at = at.run()
    assert any(t.startswith("승인") for t in texts(at))


def test_student_has_no_admin():
    service.load_roster(parse_roster((DATA / "쉬움.csv").read_bytes()), 3)
    at = log_in(start(), "2026101", "1234")
    assert "admin_start" not in keys(at)


def test_wrong_password():
    at = log_in(start(), "admin", "틀린비밀번호")
    assert "login_submit" in keys(at)
    assert any(t.startswith("막힘") for t in texts(at))


def test_container_keys_in_source():
    # st.container 의 key 는 AppTest 로 찾기 어려워 코드에서 확인한다
    src = (ROOT / "streamlit_app.py").read_text(encoding="utf-8")
    for key in ["whoami", "result", "unassigned", "assign_status"]:
        assert re.search(rf'st\.container\(key="{key}"\)', src), key
    assert 'key=f"team_{' in src
