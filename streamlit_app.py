# 생성: 2026-10-29 23:39 KST
# 팀 편성 앱 화면. 화면 요소의 key는 공고 2.7절 표와 똑같이 쓴다(자동 채점 프로그램이 key로 찾음).
import streamlit as st

import ai
import service
from config import get_secret
from roster import RosterError, parse_roster
from rules import infeasible_reason, solve

st.set_page_config(page_title="팀 편성", page_icon="👥", layout="wide")


@st.cache_resource
def _prepare_admin() -> bool:
    # 앱이 시작할 때 한 번 관리자 계정을 만들거나 비밀번호를 맞춘다(공고 2.1절)
    service.ensure_admin(get_secret("ADMIN_PASSWORD"))
    return True


def _say(msg: str) -> None:
    st.session_state.msg = msg


def _show_result() -> None:
    with st.container(key="result"):
        msg = st.session_state.get("msg")
        if msg:
            st.markdown(msg)


def _roles(s) -> str:
    return f"주 역할 {s.main_role}, 보조 역할 {', '.join(s.sub_roles) or '없음'}"


def login_view() -> None:
    st.title("팀 편성")
    with st.form("login"):
        no = st.text_input("학번", key="login_student_no")
        pw = st.text_input("비밀번호", type="password", key="login_password")
        submitted = st.form_submit_button("로그인", key="login_submit")
    if submitted:
        user = service.login(no, pw)
        if user is None:
            _say("막힘: 학번이나 비밀번호가 틀림")
        else:
            st.session_state.user = user
            _say(f"승인: {user.name}(으)로 로그인함")
            st.rerun()
    _show_result()


def render_teams(state, user=None, my_team=None, can_apply=False) -> None:
    cols = st.columns(min(len(state.teams), 4) or 1)
    for i, (n, members) in enumerate(state.teams.items()):
        with cols[i % len(cols)]:
            with st.container(key=f"team_{n}", border=True):
                mark = " (내 팀)" if n == my_team else ""
                st.markdown(f"**{state.team_names[n]}{mark}** {len(members)}/4명")
                for m in members:
                    st.markdown(f"- {m.name}: {_roles(m)}")
                if not members:
                    st.caption("빈 팀")
                if user is not None:
                    if st.button("이 팀에 지원", key=f"apply_{n}", disabled=not can_apply):
                        _say(service.apply(user.student_no, n))
                        st.rerun(scope="fragment")


def student_view(user, state) -> None:
    my_team = next((n for n, ms in state.teams.items() if any(m.student_no == user.student_no for m in ms)), None)
    # 이미 팀이 있거나, 결과를 기다리는 지원이 있거나, 마감되었으면 지원 단추를 끈다(공고 2.8절)
    can_apply = my_team is None and state.my_pending_team is None and not state.closed
    if state.closed:
        st.caption("모집이 마감됨")
    if my_team is None:
        st.caption("아직 팀이 없음")
    if state.my_pending_team is not None:
        st.caption(f"팀{state.my_pending_team} 지원의 결과를 기다리는 중")
    render_teams(state, user, my_team, can_apply)

    if my_team is None:
        return
    st.subheader("내 팀에 들어온 지원")
    pending = [p for p in state.pending if p.team_no == my_team]
    if not pending:
        st.caption("기다리는 지원이 없음")
    for p in pending:
        a = p.applicant
        st.markdown(f"**{a.name}**: {_roles(a)}")
        mine = p.votes.get(user.student_no)
        if mine:
            st.markdown(f"내 투표: {mine}")
            continue
        c1, c2 = st.columns(2)
        if c1.button("찬성", key=f"vote_yes_{a.student_no}"):
            _say(service.vote(user.student_no, a.student_no, True))
            st.rerun(scope="fragment")
        if c2.button("거부", key=f"vote_no_{a.student_no}"):
            _say(service.vote(user.student_no, a.student_no, False))
            st.rerun(scope="fragment")


def run_assign(state, status_box) -> None:
    st.session_state.plan = None
    if not state.closed:
        st.session_state.assign_log = []
        _say("막힘: 모집을 마감하지 않음")
        return
    if solve(state.teams, state.unassigned) is None:
        # 규칙을 지키는 배정이 없으면 AI를 부르지 않는다(공고 2.5절 8항)
        st.session_state.assign_log = ["규칙을 지키는 배정이 없음: " + infeasible_reason(state.teams, state.unassigned)]
        _say("막힘: 규칙을 지키는 배정이 없음")
        return
    if not state.unassigned:
        st.session_state.plan = {"assignment": [], "source": "배정할 학생 없음"}
        st.session_state.assign_log = []
        _say("승인: 배정할 학생이 없음")
        return
    with status_box:
        live = st.empty()
    result = ai.assign(state.teams, state.unassigned, lambda text: live.markdown(text), service.log_ai)
    st.session_state.plan = {"assignment": result.assignment, "source": result.source}
    st.session_state.assign_log = result.attempts + [f"배정안을 만든 곳: {result.source}"]
    _say(f"승인: 배정안을 만듦({result.source})")


def admin_view(state) -> None:
    st.subheader("1. 명단 올리기")
    file = st.file_uploader("명단 CSV", type="csv", key="admin_roster_file")
    count = st.number_input("팀 수", min_value=1, max_value=20, step=1, value=3, key="admin_team_count")
    if st.button("명단으로 처음 상태 만들기", key="admin_start"):
        if file is None:
            _say("막힘: 명단 파일을 올려 주세요")
        else:
            try:
                _say(service.load_roster(user.student_no, parse_roster(file.getvalue()), int(count)))
                st.session_state.plan = None
                st.session_state.assign_log = []
            except RosterError as e:
                _say(f"막힘: {e}")
        st.rerun(scope="fragment")

    st.subheader("2. 모집 마감")
    st.caption("마감됨" if state.closed else "모집 중")
    if st.button("모집 마감", key="admin_close"):
        _say(service.close(user.student_no))
        st.rerun(scope="fragment")
    with st.container(key="unassigned"):
        st.markdown("**팀이 없는 학생**")
        for s in state.unassigned:
            st.markdown(f"- {s.name}: {_roles(s)}")
        if not state.unassigned:
            st.caption("없음")

    st.subheader("3. AI 배정과 확정")
    clicked = st.button("AI 배정", key="admin_assign")
    status_box = st.container(key="assign_status")
    with status_box:
        for line in st.session_state.get("assign_log") or []:
            st.markdown(line)
    if clicked:
        run_assign(state, status_box)
        st.rerun(scope="fragment")

    plan = st.session_state.get("plan")
    if plan and plan["assignment"]:
        students = {s.student_no: s for s in state.unassigned}
        st.table([
            {"이름": students[no].name if no in students else no,
             "주 역할": students[no].main_role if no in students else "",
             "보조 역할": ", ".join(students[no].sub_roles) if no in students else "",
             "팀": f"팀{team}"}
            for no, team in plan["assignment"]
        ])
    if st.button("배정안 확정", key="admin_confirm"):
        if plan is None:
            _say("막힘: 확정할 배정안이 없음")
        else:
            msg = service.confirm(user.student_no, plan["assignment"])
            _say(msg)
            if msg.startswith("승인"):
                st.session_state.plan = None
                st.session_state.assign_log = []
        st.rerun(scope="fragment")

    st.subheader("팀 목록")
    render_teams(state)


@st.fragment(run_every=5)
def main_view() -> None:
    # 5초마다 바뀐 부분만 다시 그린다(3장 "다른 사람의 변경 보기"의 어려운 해결)
    user = st.session_state.user
    state = service.get_state(user.student_no)
    top1, top2 = st.columns([4, 1])
    with top1:
        with st.container(key="whoami"):
            role = "관리자" if user.is_admin else "학생"
            st.markdown(f"**{user.name}** ({user.student_no}, {role})")
    with top2:
        if st.button("로그아웃", key="logout"):
            st.session_state.clear()
            st.rerun()
    _show_result()
    if user.is_admin:
        admin_view(state)
    else:
        student_view(user, state)


_prepare_admin()
if "user" not in st.session_state:
    login_view()
else:
    main_view()
