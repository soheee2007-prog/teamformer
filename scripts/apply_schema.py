# 생성: 2026-10-29 23:27 KST
# schema.sql 을 Supabase에 실행한다. 실행: python scripts/apply_schema.py
import sys
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from config import get_secret  # noqa: E402

sql = (ROOT / "schema.sql").read_text(encoding="utf-8")
with psycopg.connect(get_secret("DATABASE_URL"), autocommit=True) as conn:
    conn.execute(sql)
print("스키마 적용 완료")
