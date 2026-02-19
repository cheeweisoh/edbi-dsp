import streamlit as st
from services.base import APIClient


class AuthService:
    def __init__(self, client: APIClient):
        self.client = client

    def login(self, username: str, password: str) -> bool:
        data = {"username": username, "password": password, "grant_type": "password"}
        response = self.client.post_form("/auth/token", data=data)

        if response.status_code == 200:
            token = response.json()["access_token"]
            st.session_state["access_token"] = token

            return True

        return False

    def logout(self):
        st.session_state.pop("access_token", None)
