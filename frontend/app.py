import os

import streamlit as st
from services.base import APIClient
from ui.dataset_page import render_dataset_page
from ui.layout import render_header, render_tabs
from ui.public import render_public_view


def main() -> None:
    if "active_dialog" not in st.session_state:
        st.session_state.active_dialog = None

    st.set_page_config(page_title="Data Sharing Platform", layout="wide")

    if "client" not in st.session_state:
        st.session_state.client = APIClient(base_url=os.getenv("API_BASE_URL", "http://localhost:8000"), api_prefix="/api/v1")
    if "page" not in st.session_state:
        st.session_state.page = "public"
    if "is_authenticated" not in st.session_state:
        st.session_state.is_authenticated = False

    if st.session_state.is_authenticated:
        render_header()

        if "selected_dataset" in st.session_state:
            render_dataset_page()
        else:
            render_tabs()
    else:
        render_public_view()


if __name__ == "__main__":
    main()
