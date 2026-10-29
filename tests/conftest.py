# 생성: 2026-10-29 23:47 KST
# 시험 전후로 관리자 계정을 ADMIN_PASSWORD 로 맞춘다.
# 시험이 관리자 비밀번호를 시험용 값으로 바꾸므로, 끝나면 되돌려 배포한 앱(같은 DB)의 관리자 로그인이 깨지지 않게 한다.
import pytest

import service
from config import get_secret


@pytest.fixture(autouse=True)
def restore_admin():
    service.ensure_admin(get_secret("ADMIN_PASSWORD"))
    yield
    service.ensure_admin(get_secret("ADMIN_PASSWORD"))
