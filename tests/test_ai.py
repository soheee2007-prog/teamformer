# 생성: 2026-10-29 23:35 KST
# ai.py 시험. caller 에 가짜 함수를 넣어 실제 모델을 부르지 않는다(무료 한도 보호).
import json
import time

import pytest

import ai
from ai import AIError, assign, call_model, parse_response
from rules import Student, check_assignment

PL, WP, FD, TT, RW, PT = "기획자", "웹 프로그래머", "프론트엔드 디자이너", "테스터", "보고서 작성자", "발표자"


def S(no, main, *subs):
    return Student(str(no), f"학생{no}", main, tuple(subs))


TEAMS = {1: [S(1, PL, RW), S(2, WP, FD)], 2: [S(3, PL, PT), S(4, TT)], 3: [S(5, FD, WP), S(6, RW, PL)]}
UNASSIGNED = [S(7, WP, TT), S(8, PT), S(9, TT, PL)]
GOOD = json.dumps({"assignments": [{"student_no": "7", "team_no": 2}, {"student_no": "8", "team_no": 3},
                                   {"student_no": "9", "team_no": 1}]})
BAD_PLAN = json.dumps({"assignments": [{"student_no": "7", "team_no": 1}, {"student_no": "8", "team_no": 3},
                                       {"student_no": "9", "team_no": 2}]})


def test_parse_variants():
    text = '배정안입니다.\n```json\n{"assignments":[{"student_no":"S7","team_no":"2"}]}\n```\n끝.'
    assert parse_response(text) == [("S7", 2)]


def test_parse_bad():
    with pytest.raises(AIError):
        parse_response("모르겠습니다")


def test_first_model_ok():
    statuses = []
    result = assign(TEAMS, UNASSIGNED, statuses.append, lambda *a: None, caller=lambda m, p: GOOD)
    assert result.source == f"1차 모델({ai.MODELS[0]})"
    assert any("1차 모델" in s for s in statuses)
    assert check_assignment(TEAMS, UNASSIGNED, result.assignment) == []


def test_fallback_on_error_and_bad_plan():
    answers = iter([AIError("HTTP 429"), BAD_PLAN, GOOD])

    def fake(model, prompt):
        a = next(answers)
        if isinstance(a, Exception):
            raise a
        return a

    logs = []
    result = assign(TEAMS, UNASSIGNED, lambda s: None, lambda *a: logs.append(a), caller=fake)
    assert result.source == f"3차 모델({ai.MODELS[2]})"
    assert len(result.attempts) == 3
    assert "HTTP 429" in result.attempts[0]
    assert "검사 실패" in result.attempts[1]
    assert len(logs) == 3


def test_all_fail_uses_solver():
    def fake(model, prompt):
        raise AIError("빈 응답")

    result = assign(TEAMS, UNASSIGNED, lambda s: None, lambda *a: None, caller=fake)
    assert result.source == "앱의 스스로 배정"
    assert check_assignment(TEAMS, UNASSIGNED, result.assignment) == []


def test_call_model_total_timeout(monkeypatch):
    def slow_post(*args, **kwargs):
        time.sleep(3)

    monkeypatch.setattr(ai.requests, "post", slow_post)
    monkeypatch.setattr(ai, "get_secret", lambda name: "가짜키")
    start = time.time()
    with pytest.raises(AIError, match="1초"):
        call_model("가짜/모델", "질문", limit_sec=1)
    assert time.time() - start < 2.5


def test_unexpected_error_moves_to_next_model():
    # AIError 가 아닌 예외(예: 응답이 JSON이 아님, 키 없음)도 실패로 보고 다음 모델로 넘어간다
    answers = iter([ValueError("JSON이 아닌 200 응답"), RuntimeError("비밀 값 없음"), GOOD])

    def fake(model, prompt):
        a = next(answers)
        if isinstance(a, Exception):
            raise a
        return a

    result = assign(TEAMS, UNASSIGNED, lambda s: None, lambda *a: None, caller=fake)
    assert result.source == f"3차 모델({ai.MODELS[2]})"
    assert "ValueError" in result.attempts[0]


def test_request_has_room_to_think(monkeypatch):
    # 추론 모델이 생각하는 데 토큰을 다 써서 빈 응답을 내지 않도록 max_tokens 를 넉넉히 준다(공고 4.3절)
    sent = {}

    class Resp:
        status_code = 200

        def json(self):
            return {"choices": [{"message": {"content": GOOD}}]}

    def fake_post(url, headers=None, json=None, timeout=None):
        sent.update(json)
        return Resp()

    monkeypatch.setattr(ai.requests, "post", fake_post)
    monkeypatch.setattr(ai, "get_secret", lambda name: "가짜키")
    call_model("가짜/모델", "질문", limit_sec=5)
    assert sent["max_tokens"] >= 16000
    assert sent["reasoning"] == {"effort": "low"}
