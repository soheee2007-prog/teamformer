# 생성: 2026-10-29 23:04 KST
# .env 값이 있는지와 DB, OpenRouter 연결을 확인한다. 비밀 값은 절대 출력하지 않는다.
# 실행: python scripts/check_connections.py
from pathlib import Path

import psycopg
import requests
from dotenv import dotenv_values

env = dotenv_values(Path(__file__).resolve().parent.parent / ".env")
names = ["OPENROUTER_API_KEY", "DATABASE_URL", "ADMIN_PASSWORD"]

print("== 1. .env 값 확인 ==")
for n in names:
    v = env.get(n) or ""
    filled = bool(v) and not v.startswith("여기에")
    print(f"{n}: {'있음' if filled else '없음'}")


def hide(text):
    # 오류 문구에 비밀 값이 섞여 있으면 가린다
    for n in names:
        if env.get(n):
            text = text.replace(env[n], "***")
    pw = (env.get("DATABASE_URL") or "").split("@")[0].rsplit(":", 1)[-1]
    return text.replace(pw, "***") if pw else text


print("\n== 2. Supabase DB 연결 ==")
try:
    with psycopg.connect(env["DATABASE_URL"], connect_timeout=15) as conn:
        ver = conn.execute("select version()").fetchone()[0]
        print("성공:", ver.split(",")[0])
except Exception as e:
    print("실패:", type(e).__name__, hide(str(e)))

print("\n== 3. OpenRouter 키 (호출 횟수를 쓰지 않는 키 정보 조회) ==")
try:
    r = requests.get(
        "https://openrouter.ai/api/v1/key",
        headers={"Authorization": f"Bearer {env['OPENROUTER_API_KEY']}"},
        timeout=20,
    )
    if r.ok:
        d = r.json().get("data", {})
        print("성공: 키가 유효함")
        print("  무료 등급:", d.get("is_free_tier"), "/ 사용 금액:", d.get("usage"))
    else:
        print("실패: HTTP", r.status_code)
except Exception as e:
    print("실패:", type(e).__name__, hide(str(e)))
