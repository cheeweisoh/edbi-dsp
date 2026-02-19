import streamlit as st
from services.base import APIClient
from services.auth_service import AuthService


def main() -> None:
    client = APIClient(base_url="http://localhost:8000", api_prefix="/api/v1")

    auth_service = AuthService(client)

    if "page" not in st.session_state:
        st.session_state.page = "public"

    st.set_page_config(page_title="Data Sharing Platform", layout="wide")

    if st.session_state.page == "public":
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")

        if st.button("Login"):
            if auth_service.login(username, password):
                st.success("Logged in!")
            else:
                st.error("Invalid credentials")


if __name__ == "__main__":
    main()
