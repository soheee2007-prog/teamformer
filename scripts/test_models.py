# 생성: 2026-10-29 23:08 KST
# 무료 모델 후보에게 작은 팀 배정 문제를 한 번씩 보내, 응답 여부, 걸린 시간, 규칙 통과를 확인한다.
# 모델마다 무료 한도 1회를 쓴다. 키 값은 출력하지 않는다.
# 실행: python scripts/test_models.py
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from dotenv import dotenv_values

env = dotenv_values(Path(__file__).resolve().parent.parent / ".env")
KEY = env["OPENROUTER_API_KEY"]
LIMIT_SEC = 120

CANDIDATES = [
    "google/gemma-4-31b-it:free",
    "google/gemma-4-26b-a4b-it:free",
    "nvidia/nemotron-3.5-super-vl:free",
    "dots-studio/dots-3-note-preview:free",
    "nvidia/nemotron-3-ultra-550b-a55b:free",
]

# 시험용 가상 상황 (실제 과제 시나리오와 다름)
STUDENTS = {
    "S1": ("기획자", ["보고서 작성자"]),
    "S2": ("웹 프로그래머", ["프론트엔드 디자이너"]),
    "S3": ("기획자", ["발표자"]),
    "S4": ("테스터", []),
    "S5": ("프론트엔드 디자이너", ["웹 프로그래머"]),
    "S6": ("보고서 작성자", ["기획자"]),
    "S7": ("웹 프로그래머", ["테스터"]),
    "S8": ("발표자", []),
    "S9": ("테스터", ["기획자"]),
}
TEAMS = {"팀1": ["S1", "S2"], "팀2": ["S3", "S4"], "팀3": ["S5", "S6"]}
UNASSIGNED = ["S7", "S8", "S9"]


def can(s, role):
    main, subs = STUDENTS[s]
    return main == role or role in subs


def check(teams):
    """배정 뒤 팀 구성이 규칙을 지키면 빈 목록, 어기면 이유 목록을 돌려준다."""
    errors = []
    for t, members in teams.items():
        if not 2 <= len(members) <= 4:
            errors.append(f"{t} 인원 {len(members)}명")
        mains = [STUDENTS[s][0] for s in members]
        if len(mains) != len(set(mains)):
            errors.append(f"{t} 주 역할 중복")
        if not any(can(a, "기획자") and can(b, "웹 프로그래머") for a in members for b in members if a != b):
            errors.append(f"{t} 기획자와 웹 프로그래머를 서로 다른 학생으로 채우지 못함")
    return errors


def build_prompt():
    lines = ["팀 프로젝트 팀 배정 문제다. 팀이 없는 학생만 팀에 넣고, 이미 팀에 있는 학생은 옮기지 않는다.", "", "학생:"]
    for s, (main, subs) in STUDENTS.items():
        lines.append(f"- {s}: 주 역할 {main}, 보조 역할 {', '.join(subs) or '없음'}")
    lines.append("\n지금 팀:")
    for t, m in TEAMS.items():
        lines.append(f"- {t}: {', '.join(m)}")
    lines.append(f"\n팀이 없는 학생: {', '.join(UNASSIGNED)}")
    lines.append(
        "\n규칙: 1) 모든 팀은 2~4명. 2) 한 팀에 주 역할이 같은 학생이 2명 이상이면 안 됨. "
        "3) 모든 팀에 기획자를 맡을 학생과 웹 프로그래머를 맡을 학생이 서로 다른 사람으로 1명씩 있어야 함(주 역할이나 보조 역할로 맡을 수 있음). "
        "4) 팀이 없는 학생은 모두 정확히 한 팀에 배정."
    )
    lines.append('\n설명 없이 JSON만 답하라. 형식: {"assignments": [{"student": "S7", "team": "팀2"}]}')
    return "\n".join(lines)


def call(model):
    r = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {KEY}"},
        json={
            "model": model,
            "messages": [{"role": "user", "content": build_prompt()}],
            "max_tokens": 4000,
            "reasoning": {"effort": "low"},
        },
        timeout=(10, LIMIT_SEC),
    )
    return r


def judge(model):
    start = time.time()
    pool = ThreadPoolExecutor(max_workers=1)
    fut = pool.submit(call, model)
    try:
        r = fut.result(timeout=LIMIT_SEC)  # 응답 시작이 아니라 전체 대기 시간을 120초로 잰다
    except FutureTimeout:
        pool.shutdown(wait=False)
        return "실패", f"{LIMIT_SEC}초 넘게 응답 없음", time.time() - start
    except Exception as e:
        return "실패", f"요청 오류 {type(e).__name__}", time.time() - start
    sec = time.time() - start
    if r.status_code != 200:
        return "실패", f"HTTP {r.status_code}", sec
    body = r.json()
    if "error" in body:
        return "실패", f"오류 응답 {body['error'].get('code')}", sec
    text = (body.get("choices") or [{}])[0].get("message", {}).get("content") or ""
    if not text.strip():
        return "실패", "빈 응답", sec
    m = re.search(r"\{.*\}", text, re.S)
    try:
        data = json.loads(m.group(0))
        result = {t: list(ms) for t, ms in TEAMS.items()}
        placed = []
        for a in data["assignments"]:
            result[a["team"]].append(a["student"])
            placed.append(a["student"])
    except Exception:
        return "실패", "JSON 형식이 아님: " + text[:80].replace("\n", " "), sec
    errors = check(result)
    if sorted(placed) != sorted(UNASSIGNED):
        errors.append(f"배정된 학생 {placed}")
    if errors:
        return "규칙 위반", "; ".join(errors), sec
    return "통과", json.dumps(data["assignments"], ensure_ascii=False), sec


if __name__ == "__main__":
    kst = timezone(timedelta(hours=9))
    print("시험 시각:", datetime.now(kst).strftime("%Y-%m-%d %H:%M KST"))
    print("검사 함수 확인(배정 전에는 팀2에 웹 프로그래머가 없어야 정상):", check(TEAMS))
    for model in CANDIDATES:
        status, detail, sec = judge(model)
        print(f"\n[{status}] {model} ({sec:.1f}초)\n  {detail}", flush=True)
