import streamlit as st
from services.auth_service import login, get_current_user


def render_header():
    st.markdown("### Data Sharing Platform")

    with st.sidebar:
        st.markdown("### User Login (Mock)")
        username = st.selectbox("Select user", ["alice", "bob", "admin"])
        login(username)

        user = get_current_user()
        st.info(
            f"Role: {user['role']}\n\nTags: {', '.join(user['tags']) if user['tags'] else 'None'}"
        )
