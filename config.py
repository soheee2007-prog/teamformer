# 생성: 2026-10-29 23:27 KST
# 비밀 값 읽기. 배포에서는 Streamlit Secrets, 내 PC에서는 .env 를 쓴다. 값은 출력하지 않는다.
import os

from dotenv import load_dotenv

load_dotenv()


def get_secret(name: str) -> str:
    try:
        import streamlit as st

        if name in st.secrets:
            return str(st.secrets[name])
    except Exception:
        pass  # secrets.toml 이 없으면 .env 로 넘어간다
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"비밀 값 없음: {name}")
    return value
