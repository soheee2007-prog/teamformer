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
