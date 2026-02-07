import streamlit as st
from ui.layout import render_header
from ui.tabs import render_tabs
from ui.pages import render_dataset_page
from ui.query import render_query_data
from services.text2sql_service import load_model

if "model" not in st.session_state:
    st.session_state["model"] = load_model()
    print("model loaded")

model = st.session_state["model"]

st.set_page_config(page_title="Data Sharing Platform", layout="wide")

render_header()

top_tabs = st.tabs(["Query Data", "All Products"])

with top_tabs[0]:
    render_query_data(model)

with top_tabs[1]:
    if "selected_dataset" in st.session_state:
        render_dataset_page()
    else:
        render_tabs()
