# 생성: 2026-10-29 23:27 KST
# 실제 Supabase에 tf_ 테이블과 제약이 있는지 확인한다.
from db import get_pool

TABLES = [
    "tf_students", "tf_student_sub_roles", "tf_teams", "tf_members",
    "tf_applications", "tf_votes", "tf_settings", "tf_ai_logs",
]


def test_tables_and_constraints():
    with get_pool().connection() as conn:
        rows = conn.execute(
            "select table_name from information_schema.tables where table_schema = 'public'"
        ).fetchall()
        names = {r[0] for r in rows}
        for t in TABLES:
            assert t in names, f"{t} 테이블이 없음"
        idx = conn.execute(
            "select 1 from pg_indexes where indexname = 'tf_applications_one_pending'"
        ).fetchone()
        assert idx is not None
