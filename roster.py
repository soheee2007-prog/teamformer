# 생성: 2026-10-29 23:25 KST
# 명단 CSV 해석(공고 2.6절). BOM이 있어도 읽고, 앞뒤 공백을 지운다.
import csv
import io

from rules import ROLES, Student

HEADER = ["student_no", "name", "main_role", "sub_roles"]


class RosterError(Exception):
    pass


def parse_roster(data: bytes) -> list[Student]:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise RosterError("CSV가 UTF-8이 아님")
    rows = [r for r in csv.reader(io.StringIO(text)) if any(c.strip() for c in r)]
    if not rows or [c.strip() for c in rows[0]] != HEADER:
        raise RosterError("첫 줄이 student_no,name,main_role,sub_roles 가 아님")
    students, seen = [], set()
    for line_no, row in enumerate(rows[1:], start=2):
        if len(row) != 4:
            raise RosterError(f"{line_no}번째 줄의 열이 4개가 아님")
        no, name, main, subs = (c.strip() for c in row)
        if not no or not name:
            raise RosterError(f"{line_no}번째 줄에 학번이나 이름이 없음")
        if no == "admin":
            raise RosterError("학번 admin 은 관리자용이라 쓸 수 없음")
        if no in seen:
            raise RosterError(f"학번이 겹침: {no}")
        sub_roles = tuple(r.strip() for r in subs.split(";") if r.strip())
        for role in (main, *sub_roles):
            if role not in ROLES:
                raise RosterError(f"{line_no}번째 줄의 역할이 6개 역할이 아님: {role}")
        if len(sub_roles) > 2:
            raise RosterError(f"{line_no}번째 줄의 보조 역할이 2개보다 많음")
        seen.add(no)
        students.append(Student(no, name, main, sub_roles))
    if not students:
        raise RosterError("명단에 학생이 없음")
    return students
