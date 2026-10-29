# 생성: 2026-10-29 23:27 KST
# DB 연결 풀을 한 번만 만들어 다시 쓴다(공고 4.2절).
import streamlit as st
from psycopg_pool import ConnectionPool

from config import get_secret


@st.cache_resource
def get_pool() -> ConnectionPool:
    # check: 앱이 잠든 사이 끊긴 연결을 꺼낼 때 걸러 내고 새로 연결한다
    return ConnectionPool(
        get_secret("DATABASE_URL"),
        min_size=1,
        max_size=5,
        check=ConnectionPool.check_connection,
        kwargs={"autocommit": True, "prepare_threshold": None},
        open=True,
    )
