# 생성: 2026-10-29 23:35 KST
# AI 배정: 1, 2, 3차 모델을 차례로 부르고, 모델마다 전체 120초를 재서 끊는다.
# 응답은 규칙으로 검사하고, 3차까지 실패하면 앱이 스스로 배정한다(PRD 4.5~4.6절, 공고 4.3절).
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import dataclass
from typing import Callable

import requests

from config import get_secret
from rules import Student, check_assignment, solve

# 2026-10-29 시험 결과로 정한 차례(docs/evidence/model-test-2026-10-29.txt)
MODELS = [
    "nvidia/nemotron-3.5-super-vl:free",
    "google/gemma-4-31b-it:free",
    "dots-studio/dots-3-note-preview:free",
]
LIMIT_SEC = 120
URL = "https://openrouter.ai/api/v1/chat/completions"


class AIError(Exception):
    pass


@dataclass
class AssignResult:
    assignment: list[tuple[str, int]]
    source: str
    attempts: list[str]


def _describe(s: Student) -> str:
    return f"{s.student_no} {s.name} (주 역할 {s.main_role}, 보조 역할 {', '.join(s.sub_roles) or '없음'})"


def build_prompt(teams: dict[int, list[Student]], unassigned: list[Student]) -> str:
    lines = ["팀 프로젝트의 팀 배정 문제다. 팀이 없는 학생만 팀에 넣고, 이미 팀에 있는 학생은 옮기지 않는다.", "", "지금 팀:"]
    for n in sorted(teams):
        members = "; ".join(_describe(s) for s in teams[n]) or "빈 팀"
        lines.append(f"- 팀 번호 {n}: {members}")
    lines.append("")
    lines.append("팀이 없는 학생:")
    lines.extend(f"- {_describe(s)}" for s in unassigned)
    lines.append("")
    lines.append("규칙:")
    lines.append("1) 배정 뒤 모든 팀은 2~4명이어야 한다.")
    lines.append("2) 한 팀에 주 역할이 같은 학생이 2명 이상이면 안 된다.")
    lines.append("3) 모든 팀에 기획자를 맡을 학생과 웹 프로그래머를 맡을 학생이 서로 다른 사람으로 1명씩 있어야 한다. "
                 "주 역할이나 보조 역할로 맡을 수 있다.")
    lines.append("4) 팀이 없는 학생은 모두 정확히 한 팀에 배정한다.")
    lines.append("")
    lines.append('설명 없이 JSON만 답하라. 형식: {"assignments": [{"student_no": "학번", "team_no": 팀 번호}]}')
    return "\n".join(lines)


def parse_response(text: str) -> list[tuple[str, int]]:
    m = re.search(r"\{.*\}", text, re.S)
    try:
        data = json.loads(m.group(0))
        return [(str(a["student_no"]).strip(), int(a["team_no"])) for a in data["assignments"]]
    except Exception:
        raise AIError("JSON 형식이 아님")


def _post(model: str, prompt: str, limit_sec: float):
    return requests.post(
        URL,
        headers={"Authorization": f"Bearer {get_secret('OPENROUTER_API_KEY')}"},
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 16000,  # 생각에 토큰을 많이 써도 답을 낼 여유를 둠
            "reasoning": {"effort": "low"},  # 추론 모델이 빈 응답을 내지 않도록(공고 4.3절)
        },
        timeout=(10, limit_sec),
    )


def call_model(model: str, prompt: str, limit_sec: float = LIMIT_SEC) -> str:
    """요청한 때부터 응답을 다 받을 때까지 전체 시간을 limit_sec 으로 제한한다."""
    pool = ThreadPoolExecutor(max_workers=1)
    future = pool.submit(_post, model, prompt, limit_sec)
    try:
        r = future.result(timeout=limit_sec)
    except FutureTimeout:
        raise AIError(f"{limit_sec:g}초 넘게 응답 없음")
    except requests.RequestException as e:
        raise AIError(f"요청 오류 {type(e).__name__}")
    finally:
        pool.shutdown(wait=False)  # 늦게 오는 응답은 기다리지 않고 버린다
    if r.status_code != 200:
        raise AIError(f"HTTP {r.status_code}")
    body = r.json()
    if "error" in body:
        raise AIError(f"오류 응답 {body['error'].get('code')}")
    text = ((body.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
    if not text.strip():
        raise AIError("빈 응답")
    return text


def assign(
    teams: dict[int, list[Student]],
    unassigned: list[Student],
    on_status: Callable[[str], None],
    log: Callable[[str, str, str, float], None],
    caller: Callable[[str, str], str] = call_model,
) -> AssignResult:
    prompt = build_prompt(teams, unassigned)
    attempts = []
    for n, model in enumerate(MODELS, start=1):
        on_status(f"{n}차 모델({model})의 응답을 기다리는 중(최대 {LIMIT_SEC}초)")
        start = time.time()
        try:
            plan = parse_response(caller(model, prompt))
            errors = check_assignment(teams, unassigned, plan)
            if errors:
                raise AIError("검사 실패: " + "; ".join(errors[:3]))
        except Exception as e:  # 예상 못 한 오류도 실패로 보고 다음 모델로 넘어간다(PRD 4.5절 4항)
            if not isinstance(e, AIError):
                e = AIError(f"예상 못 한 오류 {type(e).__name__}")
            sec = time.time() - start
            attempts.append(f"{n}차 실패: {e} ({sec:.1f}초)")
            log(model, "실패", str(e), sec)
            continue
        sec = time.time() - start
        attempts.append(f"{n}차 성공 ({sec:.1f}초)")
        log(model, "성공", "검사 통과", sec)
        return AssignResult(plan, f"{n}차 모델({model})", attempts)
    on_status("3차 모델까지 실패해 앱이 스스로 배정하는 중")
    plan = solve(teams, unassigned) or []
    return AssignResult(plan, "앱의 스스로 배정", attempts)
