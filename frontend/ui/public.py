import streamlit as st
from services.auth_service import AuthService


@st.dialog("Sign In")
def sign_in_dialog() -> None:
    auth_service = AuthService(st.session_state.client)

    with st.form("signin_form"):
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_password")
        submitted = st.form_submit_button("Sign in")
    if submitted:
        if not email or not password:
            st.error("Email and password are required")
        else:
            try:
                auth_service.login(email, password)
                st.rerun()
            except Exception as e:
                st.error(e.message)


# @st.dialog("Sign Up")
# def sign_up_dialog() -> None:
#     with st.form("signup_form"):
#         reg_email = st.text_input("Email", key="register_email")
#         reg_password = st.text_input("Password", type="password", key="register_password")
#         reg_name = st.text_input("Display name", key="register_name")
#         reg_household = st.text_input("Household name (optional)", key="register_household")
#         submitted = st.form_submit_button("Create account")
#     if submitted:
#         if not reg_email or not reg_password:
#             st.error("Email and password are required")
#         else:
#             try:
#                 register_user(reg_email, reg_password, reg_name, reg_household)
#                 st.success("Account created. Please sign in.")
#             except APIError as err:
#                 st.error(err.message)


def render_public_view() -> None:
    if "show_sign_in_form" not in st.session_state:
        st.session_state.show_sign_in_form = False
    if "sign_in_form_data" not in st.session_state:
        st.session_state.sign_in_form_data = {"email": "", "password": ""}

    st.markdown("<h1 style='text-align: center;'>Data Sharing Platform</h1>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    col1, col2, col3 = st.columns([2, 3, 2])
    with col2:
        if st.button("Sign In", key="landing_signin", use_container_width=True):
            st.session_state.show_sign_in_form = True
            if st.session_state.show_sign_in_form:
                sign_in_dialog()
            else:
                st.session_state.sign_in_form_data = {"email": "", "password": ""}
        # if st.button("Sign Up", key="landing_signup", use_container_width=True):
        #     st.session_state.show_sign_up_form = True
        #     if st.session_state.show_sign_up_form:
        #         sign_up_dialog()
