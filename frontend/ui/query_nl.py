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

    col1, col2 = st.columns([1, 6])
    with col1:
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
                st.text(sql)
            #             df = con.execute(sql).fetchdf()
            #
            #             st.session_state.ask_data_history.append(
            #                 {"user": user_input, "sql": sql, "df": df}
            #             )
            #
            #             if df.empty:
            #                 st.info("No results returned.")
            #             else:
            #                 st.dataframe(df)
            #
            except Exception as e:
                st.error(f"Error: {str(e)}")
