# 생성: 2026-10-29 23:36 KST
# ai.assign 을 실제 모델로 한 번 실행해 본다(무료 한도 1~3회 사용). DB는 쓰지 않는다.
# 상황: 공고 부록 2 중간 시나리오의 마감 직후. 실행: python scripts/try_ai_assign.py
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ai import assign  # noqa: E402
from roster import parse_roster  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
students = {s.student_no: s for s in parse_roster((ROOT / "tests/data/중간.csv").read_bytes())}
teams = {1: [students["2026201"], students["2026205"]], 2: [students["2026206"], students["2026209"]], 3: [], 4: []}
placed = {s.student_no for ms in teams.values() for s in ms}
unassigned = [s for no, s in students.items() if no not in placed]

print("실행 시각:", datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d %H:%M KST"))
result = assign(teams, unassigned, lambda m: print("[안내]", m, flush=True), lambda *a: None)
print("만든 곳:", result.source)
for a in result.attempts:
    print(" ", a)
for no, team in result.assignment:
    print(f"  {students[no].name} -> 팀{team}")
