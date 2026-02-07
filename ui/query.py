import streamlit as st
from services.text2sql_service import text_to_sql
from metadata.datasets import DATASETS
from services.storage_service import con


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
            try:
                sql = text_to_sql(user_input, DATASETS, model)
                df = con.execute(sql).fetchdf()

                st.session_state.ask_data_history.append(
                    {"user": user_input, "sql": sql, "df": df}
                )

                if df.empty:
                    st.info("No results returned.")
                else:
                    st.dataframe(df)

            except Exception as e:
                st.error(f"Error: {str(e)}")
