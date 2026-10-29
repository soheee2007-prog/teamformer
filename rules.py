# 생성: 2026-10-29 23:25 KST
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
