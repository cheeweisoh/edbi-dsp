import streamlit as st
from services.base import APIClient


class AuthService:
    def __init__(self, client: APIClient):
        self.client = client

    def login(self, username: str, password: str) -> bool:
        st.session_state["is_authenticated"] = False

        data = {"username": username, "password": password, "grant_type": "password"}
        response = self.client.post_form("/auth/token", data=data)

        if response.status_code == 200:
            token = response.json()["access_token"]
            st.session_state["access_token"] = token
            st.session_state["is_authenticated"] = True

        return st.session_state.get("is_authenticated", False)

    def logout(self):
        st.session_state.pop("access_token", None)
        st.session_state["is_authenticated"] = False
