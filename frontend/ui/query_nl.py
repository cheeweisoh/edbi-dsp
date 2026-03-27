import pandas as pd
import streamlit as st
from services.query_service import QueryService


def render_query_data():
    query_service = QueryService(st.session_state.client)

    if "ask_data_history" not in st.session_state:
        st.session_state.ask_data_history = []

    user_input = st.text_area(
        "Describe your query",
        placeholder="e.g. Show me the number of cases that started in each year.",
        height=120,
    )

    submit = st.button("Generate SQL", width="stretch")

    if submit and user_input.strip():
        with st.spinner("Generating SQL..."):
            try:
                response = query_service.query_nl(user_input)
                if response.status_code != 200:
                    detail = response.json().get("detail", response.text)
                    st.error(f"Error: {detail}")
                    return
                sql = response.json().get("sql", "")

                query_response = query_service.query_sql(sql)
                if query_response.status_code != 200:
                    detail = query_response.json().get("detail", query_response.text)
                    st.error(f"Error: {detail}")
                    return

                result = query_response.json()
                df = pd.DataFrame(result.get("rows", []), columns=result.get("columns", []))
                st.markdown("#### Query Result")
                if not df.empty:
                    st.dataframe(df, width="stretch", hide_index=True)
                else:
                    st.info("No results returned.")

                with st.expander("SQL Query", expanded=False):
                    st.code(sql, language="sql")

            except Exception as e:
                st.error(f"Error: {str(e)}")
