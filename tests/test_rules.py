# 생성: 2026-10-29 23:25 KST
# rules.py 의 팀 규칙 시험. 공고 2.3절, 3장의 예를 그대로 쓴다.
from rules import Student, apply_block_reason, filled_required, team_errors

PL, WP, FD, TT, RW, PT = "기획자", "웹 프로그래머", "프론트엔드 디자이너", "테스터", "보고서 작성자", "발표자"


def S(no, main, *subs):
    return Student(str(no), f"학생{no}", main, tuple(subs))


# ---- 과제 2: 팀 규칙 ----

def test_filled_required_one_person_counts_once():
    assert filled_required([S(1, PL, WP)]) == 1


def test_filled_required_two_people():
    assert filled_required([S(1, TT, PL), S(2, FD, WP)]) == 2


def test_block_full():
    members = [S(1, PL), S(2, WP), S(3, FD), S(4, TT)]
    assert apply_block_reason(members, S(5, RW)) == "팀이 꽉 참"


def test_block_same_main():
    assert apply_block_reason([S(1, PL), S(2, WP)], S(3, PL)) == "같은 주 역할의 팀원이 있음"


def test_block_required_slot():
    assert apply_block_reason([S(1, TT), S(2, PT)], S(3, RW)) == "필수 포함 역할을 맡을 학생의 자리가 모자람"


def test_block_required_slot_ok():
    assert apply_block_reason([S(1, PL, PT), S(2, FD, TT)], S(3, WP, FD)) is None


def test_empty_team_never_blocked():
    assert apply_block_reason([], S(1, RW)) is None


def test_team_errors_ok_and_bad():
    assert team_errors(1, [S(1, PL), S(2, WP)]) == []
    assert any("인원 1명" in e for e in team_errors(1, [S(1, PL)]))
    assert any("주 역할 중복" in e for e in team_errors(2, [S(1, TT), S(2, TT)]))


# ---- 과제 3: 배정안 검사와 스스로 배정 ----
from rules import check_assignment, infeasible_reason, solve  # noqa: E402


def small_case():
    # scripts/test_models.py 와 같은 상황
    teams = {1: [S(1, PL, RW), S(2, WP, FD)], 2: [S(3, PL, PT), S(4, TT)], 3: [S(5, FD, WP), S(6, RW, PL)]}
    unassigned = [S(7, WP, TT), S(8, PT), S(9, TT, PL)]
    return teams, unassigned


def test_check_ok():
    teams, un = small_case()
    assert check_assignment(teams, un, [("7", 2), ("8", 3), ("9", 1)]) == []


def test_check_missing_student():
    teams, un = small_case()
    assert "배정되지 않은 학생: 9" in check_assignment(teams, un, [("7", 2), ("8", 3)])


def test_check_duplicate_student():
    teams, un = small_case()
    errors = check_assignment(teams, un, [("7", 2), ("7", 3), ("8", 3), ("9", 1)])
    assert "두 번 이상 배정된 학생: 7" in errors


def test_check_unknown_and_moved():
    teams, un = small_case()
    errors = check_assignment(teams, un, [("7", 9), ("1", 2), ("8", 3), ("9", 1)])
    assert "없는 팀: 9" in errors
    assert "팀이 없는 학생이 아님: 1" in errors


def test_check_rule_break():
    teams, un = small_case()
    errors = check_assignment(teams, un, [("7", 1), ("8", 3), ("9", 2)])
    assert any(e.startswith("팀2") for e in errors)


def test_solve_finds_valid():
    teams, un = small_case()
    plan = solve(teams, un)
    assert plan is not None and check_assignment(teams, un, plan) == []


def test_solve_medium_scenario():
    # 공고 부록 2 중간 시나리오의 마감 직후 상태
    teams = {
        1: [S(2026201, PL, PT, TT), S(2026205, WP, TT)],
        2: [S(2026206, WP, FD), S(2026209, FD, WP)],
        3: [],
        4: [],
    }
    un = [S(2026202, PL, TT), S(2026203, PL, RW), S(2026204, PL), S(2026207, WP),
          S(2026208, WP, PT), S(2026210, TT, PL), S(2026211, RW), S(2026212, PT, RW, FD)]
    plan = solve(teams, un)
    assert plan is not None and check_assignment(teams, un, plan) == []


def test_solve_none_and_reason():
    teams = {1: [S(1, TT), S(2, PT), S(3, RW), S(4, FD)], 2: [S(5, PL), S(6, WP)]}
    un = [S(7, PL)]
    assert solve(teams, un) is None
    reason = infeasible_reason(teams, un)
    assert "팀1" in reason and "웹 프로그래머" in reason


def test_reason_no_candidate():
    teams = {1: [S(1, PL), S(2, WP)], 2: [S(3, PL), S(4, TT)]}
    un = [S(5, FD), S(6, RW)]
    assert solve(teams, un) is None
    assert infeasible_reason(teams, un) == "팀2에 웹 프로그래머를 맡을 학생이 없음"
