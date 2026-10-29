# 생성: 2026-10-29 23:25 KST
# 명단 CSV 해석 시험(공고 2.6절).
from pathlib import Path

import pytest

from roster import RosterError, parse_roster

DATA = Path(__file__).parent / "data"
HEAD = "student_no,name,main_role,sub_roles\n"


def test_parse_practice_files():
    counts = {name: len(parse_roster((DATA / name).read_bytes())) for name in ["쉬움.csv", "중간.csv", "어려움.csv"]}
    assert counts == {"쉬움.csv": 8, "중간.csv": 12, "어려움.csv": 16}
    s8 = [s for s in parse_roster((DATA / "쉬움.csv").read_bytes()) if s.student_no == "2026108"][0]
    assert s8.main_role == "테스터" and s8.sub_roles == ("보고서 작성자", "발표자")


def test_bom_and_spaces():
    data = ("﻿" + HEAD + " 2026001 , 가나다 , 기획자 , 보고서 작성자 \n").encode("utf-8")
    s = parse_roster(data)[0]
    assert s.student_no == "2026001" and s.name == "가나다" and s.sub_roles == ("보고서 작성자",)


def test_empty_sub_roles():
    s = parse_roster((HEAD + "2026002,라마바,웹 프로그래머,\n").encode())[0]
    assert s.sub_roles == ()


def test_bad_role():
    with pytest.raises(RosterError, match="디자이너"):
        parse_roster((HEAD + "2026003,사아자,디자이너,\n").encode())


def test_bad_columns():
    with pytest.raises(RosterError):
        parse_roster((HEAD + "2026004,차카타,테스터\n").encode())


def test_duplicate_student_no():
    with pytest.raises(RosterError):
        parse_roster((HEAD + "2026005,가,테스터,\n2026005,나,발표자,\n").encode())


def test_admin_student_no_rejected():
    with pytest.raises(RosterError):
        parse_roster((HEAD + "admin,관리,테스터,\n").encode())
