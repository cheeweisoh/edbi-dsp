import streamlit as st
from services.text2sql_service import text_to_sql
from metadata.datasets import DATASETS


def render_query_data(model):
    st.subheader("Ask Your Data")
    st.caption(
        "Describe the data you want in natural language. We'll generate SQL for you."
    )

    if "ask_data_history" not in st.session_state:
        st.session_state.ask_data_history = []

    user_input = st.text_area(
        "Describe your query",
        placeholder="e.g. Show me total electricity sales by sector for 2024",
        height=120,
    )

    col1, col2 = st.columns([1, 6])
    with col1:
        submit = st.button("Generate SQL", width="stretch")

    if submit and user_input.strip():
        with st.spinner("Generating SQL..."):
            sql = text_to_sql(user_input, DATASETS, model)

        st.session_state.ask_data_history.append({"user": user_input, "sql": sql})

    for msg in reversed(st.session_state.ask_data_history):
        st.markdown(f"**You:** {msg['user']}")
        st.code(msg["sql"], language="sql")
