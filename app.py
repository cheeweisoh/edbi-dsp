import streamlit as st
from ui.layout import render_header
from ui.tabs import render_tabs
from ui.pages import render_dataset_page

st.set_page_config(page_title="Data Sharing Platform", layout="wide")

render_header()

if "selected_dataset" in st.session_state:
    render_dataset_page()
else:
    render_tabs()
