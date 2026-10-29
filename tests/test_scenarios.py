# 생성: 2026-10-29 23:32 KST
# 공고 부록의 연습 시나리오 3개를 service.py 로 처음부터 끝까지 실행한다.
# 단계마다 안내의 첫 단어가 기대 결과와 같은지, 확정 뒤 모든 팀이 규칙을 지키는지 확인한다.
# 시나리오는 이 시험 파일에만 있고 앱 코드에는 없다(공고 6.3절 19번).
from pathlib import Path

import service
from roster import parse_roster
from rules import solve, team_errors

DATA = Path(__file__).parent / "data"


def run(csv_name: str, team_count: int, steps: list[tuple]):
    service.load_roster(parse_roster((DATA / csv_name).read_bytes()), team_count)
    for i, step in enumerate(steps, start=1):
        kind, *args, expected = step
        if kind == "apply":
            msg = service.apply(args[0], args[1])
        elif kind == "vote":
            msg = service.vote(args[0], args[1], args[2])
        elif kind == "close":
            msg = service.close()
        else:
            raise ValueError(kind)
        assert msg.split(":")[0] == expected, f"{i}번째 동작 {step} -> {msg}"


def assign_and_confirm():
    state = service.get_state()
    plan = solve(state.teams, state.unassigned)
    assert plan is not None
    assert service.confirm(plan).startswith("승인")
    state = service.get_state()
    assert state.unassigned == []
    for n, members in state.teams.items():
        assert team_errors(n, members) == [], f"팀{n} 규칙 위반"


def unassigned_nos():
    return {s.student_no for s in service.get_state().unassigned}


def test_easy():
    run("쉬움.csv", 3, [
        ("apply", "2026101", 1, "승인"), ("apply", "2026102", 2, "승인"), ("apply", "2026103", 3, "승인"),  # 1
        ("apply", "2026104", 1, "대기"), ("vote", "2026101", "2026104", True, "승인"),  # 2
        ("apply", "2026105", 2, "대기"), ("vote", "2026102", "2026105", True, "승인"),  # 3
        ("apply", "2026107", 1, "대기"), ("vote", "2026101", "2026107", True, "대기"),
        ("vote", "2026104", "2026107", False, "거절"),  # 4
        ("apply", "2026106", 3, "대기"), ("vote", "2026103", "2026106", True, "승인"),  # 5
        ("close", "승인"),  # 6
    ])
    assign_and_confirm()


def test_medium():
    run("중간.csv", 4, [
        ("apply", "2026201", 1, "승인"),  # 1
        ("apply", "2026205", 1, "대기"), ("vote", "2026201", "2026205", True, "승인"),  # 2
        ("apply", "2026202", 1, "막힘"),  # 3 주 역할 중복
        ("apply", "2026206", 2, "승인"),  # 4
        ("apply", "2026209", 2, "대기"), ("vote", "2026206", "2026209", True, "승인"),  # 5
        ("apply", "2026210", 2, "대기"), ("vote", "2026206", "2026210", True, "대기"),
        ("vote", "2026209", "2026210", False, "거절"),  # 6
        ("apply", "2026203", 3, "승인"), ("apply", "2026211", 4, "승인"),  # 7
        ("apply", "2026212", 4, "대기"), ("apply", "2026212", 3, "막힘"),  # 8
        ("close", "승인"),  # 9
    ])
    assert {"2026203", "2026211", "2026212"} <= unassigned_nos()
    assert service.get_state().pending == []
    assert service.apply("2026202", 3).startswith("막힘")  # 10 마감
    assign_and_confirm()  # 11


def test_hard():
    run("어려움.csv", 4, [
        ("apply", "2026301", 1, "승인"),  # 1
        ("apply", "2026304", 1, "대기"), ("vote", "2026301", "2026304", True, "승인"),  # 2
        ("apply", "2026307", 1, "대기"), ("vote", "2026301", "2026307", True, "대기"),
        ("vote", "2026304", "2026307", True, "승인"),  # 3
        ("apply", "2026302", 2, "승인"),  # 4
        ("apply", "2026308", 2, "대기"), ("vote", "2026302", "2026308", True, "승인"),  # 5
        ("apply", "2026305", 2, "대기"), ("apply", "2026306", 2, "대기"),  # 6
        ("vote", "2026302", "2026305", True, "대기"), ("vote", "2026308", "2026305", True, "승인"),  # 7
        ("vote", "2026302", "2026306", True, "대기"), ("vote", "2026308", "2026306", True, "대기"),
        ("vote", "2026305", "2026306", True, "거절"),  # 8 승인 직전 재검사
        ("apply", "2026311", 3, "승인"),  # 9
        ("apply", "2026315", 3, "대기"), ("vote", "2026311", "2026315", True, "승인"),  # 10
        ("apply", "2026314", 3, "막힘"),  # 11 필수 포함 역할 자리
        ("apply", "2026310", 4, "승인"),  # 12
        ("apply", "2026313", 1, "대기"), ("vote", "2026301", "2026313", True, "대기"),  # 13
        ("close", "승인"),  # 14
    ])
    assert {"2026313", "2026310"} <= unassigned_nos()
    assign_and_confirm()  # 15
