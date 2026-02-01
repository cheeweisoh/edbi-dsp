import streamlit as st


def dataset_card(ds: dict, prefix: None) -> None:
    with st.container(border=True):
        st.markdown(f"#### {ds['title']}")
        st.markdown(f"**Agency:** {ds['agency']}")
        st.markdown(ds["description"])
        st.caption(f"{ds['update_frequency']} | {ds['coverage_period']}")

        if st.button("Learn more", key=f"{ds['id']}_{prefix}"):
            st.session_state["selected_dataset"] = ds["id"]
            st.rerun()
