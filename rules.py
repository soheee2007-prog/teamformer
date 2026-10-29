# 생성: 2026-10-29 23:28 KST
# 팀 규칙 검사, 배정안 검사, 스스로 배정. DB와 화면을 모르는 순수 함수만 둔다(PRD 3절, 4.6절).
from dataclasses import dataclass

ROLES = ("기획자", "웹 프로그래머", "프론트엔드 디자이너", "테스터", "보고서 작성자", "발표자")
PLANNER = "기획자"
WEB = "웹 프로그래머"
MAX_SIZE = 4
MIN_SIZE = 2


@dataclass(frozen=True)
class Student:
    student_no: str
    name: str
    main_role: str
    sub_roles: tuple[str, ...] = ()


def can_take(s: Student, role: str) -> bool:
    return s.main_role == role or role in s.sub_roles


def filled_required(members: list[Student]) -> int:
    """기획자와 웹 프로그래머를 서로 다른 학생에게 맡길 때 채울 수 있는 최대 수(0~2)."""
    planners = [s for s in members if can_take(s, PLANNER)]
    webs = [s for s in members if can_take(s, WEB)]
    if any(a != b for a in planners for b in webs):
        return 2
    return 1 if planners or webs else 0


def apply_block_reason(members: list[Student], applicant: Student) -> str | None:
    if len(members) >= MAX_SIZE:
        return "팀이 꽉 참"
    if any(m.main_role == applicant.main_role for m in members):
        return "같은 주 역할의 팀원이 있음"
    left = MAX_SIZE - (len(members) + 1)
    missing = 2 - filled_required(members + [applicant])
    if left < missing:
        return "필수 포함 역할을 맡을 학생의 자리가 모자람"
    return None


def team_errors(team_no: int, members: list[Student]) -> list[str]:
    errors = []
    name = f"팀{team_no}"
    if not MIN_SIZE <= len(members) <= MAX_SIZE:
        errors.append(f"{name} 인원 {len(members)}명")
    mains = [m.main_role for m in members]
    if len(mains) != len(set(mains)):
        errors.append(f"{name} 주 역할 중복")
    if filled_required(members) < 2:
        has_pl = any(can_take(m, PLANNER) for m in members)
        has_wp = any(can_take(m, WEB) for m in members)
        if not has_pl:
            errors.append(f"{name}에 기획자를 맡을 학생이 없음")
        if not has_wp:
            errors.append(f"{name}에 웹 프로그래머를 맡을 학생이 없음")
        if has_pl and has_wp:
            errors.append(f"{name}에 기획자와 웹 프로그래머를 서로 다른 학생으로 채울 수 없음")
    return errors


Assignment = list[tuple[str, int]]


def check_assignment(teams: dict[int, list[Student]], unassigned: list[Student], assignment: Assignment) -> list[str]:
    """배정안이 공고 2.5절 4항의 다섯 가지 검사를 통과하면 빈 목록을 돌려준다."""
    errors = []
    waiting = {s.student_no: s for s in unassigned}
    in_team = {m.student_no for ms in teams.values() for m in ms}
    result = {n: list(ms) for n, ms in teams.items()}
    seen = set()
    for no, team_no in assignment:
        if no in seen:
            errors.append(f"두 번 이상 배정된 학생: {no}")
            continue
        seen.add(no)
        if team_no not in teams:
            errors.append(f"없는 팀: {team_no}")
        elif no in in_team:
            errors.append(f"팀이 없는 학생이 아님: {no}")
        elif no not in waiting:
            errors.append(f"없는 학생: {no}")
        else:
            result[team_no].append(waiting[no])
    for no in waiting:
        if no not in seen:
            errors.append(f"배정되지 않은 학생: {no}")
    for n in sorted(result):
        errors.extend(team_errors(n, result[n]))
    return errors


def _fits(members: list[Student], s: Student) -> bool:
    return len(members) < MAX_SIZE and all(m.main_role != s.main_role for m in members)


def solve(teams: dict[int, list[Student]], unassigned: list[Student]) -> Assignment | None:
    """규칙을 모두 지키는 배정을 백트래킹으로 끝까지 찾는다. 없으면 None."""
    result = {n: list(ms) for n, ms in teams.items()}
    # 들어갈 수 있는 팀이 적은 학생부터 넣어 빨리 끝낸다
    order = sorted(unassigned, key=lambda s: sum(_fits(ms, s) for ms in result.values()))
    plan: Assignment = []

    def need(i: int) -> bool:
        # 남은 학생으로 모든 팀을 최소 인원까지 채울 수 있는가
        short = sum(max(0, MIN_SIZE - len(ms)) for ms in result.values())
        return short <= len(order) - i

    def go(i: int) -> bool:
        if i == len(order):
            return all(not team_errors(n, ms) for n, ms in result.items())
        if not need(i):
            return False
        s = order[i]
        for n in sorted(result):
            if _fits(result[n], s):
                result[n].append(s)
                plan.append((s.student_no, n))
                if go(i + 1):
                    return True
                result[n].pop()
                plan.pop()
        return False

    return list(plan) if go(0) else None


def infeasible_reason(teams: dict[int, list[Student]], unassigned: list[Student]) -> str:
    """규칙을 지키는 배정이 없을 때 그 이유를 한 문장으로 돌려준다(PRD 4.6절 순서)."""
    free = sum(MAX_SIZE - len(ms) for ms in teams.values())
    if len(unassigned) > free:
        return f"팀이 없는 학생 {len(unassigned)}명이 빈자리 {free}개보다 많음"
    short = sum(max(0, MIN_SIZE - len(ms)) for ms in teams.values())
    if short > len(unassigned):
        return f"모든 팀을 2명 이상으로 채울 학생이 모자람(필요 {short}명, 남은 학생 {len(unassigned)}명)"
    for n in sorted(teams):
        ms = teams[n]
        missing = [r for r in (PLANNER, WEB) if not any(can_take(m, r) for m in ms)]
        if len(ms) >= MAX_SIZE and team_errors(n, ms):
            if missing:
                return f"팀{n}은 꽉 찼는데 {', '.join(missing)}를 맡을 학생이 없음"
            return f"팀{n}은 꽉 찼는데 기획자와 웹 프로그래머를 서로 다른 학생으로 채울 수 없음"
    for n in sorted(teams):
        ms = teams[n]
        for r in (PLANNER, WEB):
            if any(can_take(m, r) for m in ms):
                continue
            if not any(can_take(s, r) and _fits(ms, s) for s in unassigned):
                return f"팀{n}에 {r}를 맡을 학생이 없음"
    return "팀마다 따로는 가능하지만 함께 만족하는 조합이 없음"
