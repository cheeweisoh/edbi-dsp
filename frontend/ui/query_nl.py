import pandas as pd
import streamlit as st
from services.query_service import QueryService


def render_query_data():
    query_service = QueryService(st.session_state.client)
    # user = get_current_user()

    if "ask_data_history" not in st.session_state:
        st.session_state.ask_data_history = []

    user_input = st.text_area(
        "Describe your query",
        placeholder="e.g. Show me total electricity sales by sector for 2024",
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
                # st.markdown("#### Generated SQL")
                # st.code(sql, language="sql")

                query_response = query_service.query_sql(sql)
                if query_response.status_code != 200:
                    detail = query_response.json().get("detail", query_response.text)
                    st.error(f"Error: {detail}")
                    return

                result = query_response.json()
                df = pd.DataFrame(result.get("rows", []), columns=result.get("columns", []))
                st.markdown("#### Query Result")
                if df.empty:
                    st.info("No results returned.")
                else:
                    st.dataframe(df, width="stretch")
            except Exception as e:
                st.error(f"Error: {str(e)}")
