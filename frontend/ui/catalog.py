import streamlit as st
from services.dataset_service import DatasetService


def search_datasets(search: str, datasets: list[dict]) -> list[dict]:
    query = search.strip().lower()
    if not query:
        return datasets

    filtered: list[dict] = []
    for dataset in datasets:
        title = str(dataset.get("title") or dataset.get("name") or "")
        description = str(dataset.get("description") or "")
        if query in title.lower() or query in description.lower():
            filtered.append(dataset)
    return filtered


def dataset_card(ds: dict, prefix: str | None) -> None:
    with st.container(border=True):
        st.markdown(f"#### {ds['name']}")
        # st.markdown(f"**Agency:** {ds['agency']}")
        st.markdown(ds["description"])
        # st.caption(f"{ds['update_frequency']} | {ds['coverage_period']}")

        if st.button("Learn more", key=f"{ds['id']}_{prefix}"):
            st.session_state["selected_dataset"] = ds["id"]
            st.rerun()


def render_catalog() -> None:
    dataset_service = DatasetService(st.session_state.client)

    search = st.text_input("Search keywords")
    visible_datasets = dataset_service.list().json()
    filtered_datasets = search_datasets(search, visible_datasets)

    # tabs = st.tabs(
    #     [
    #         "All Products",
    #     ]
    # )

    # with tabs[0]:
    #     popular_datasets = search_datasets(search, category="Popular", datasets=visible_datasets)
    #     cols = st.columns(4)
    #     for i, ds in enumerate(popular_datasets):
    #         with cols[i % 4]:
    #             dataset_card(ds, "popular")
    #
    # with tabs[0]:
    # all_datasets = search_datasets(search, datasets=visible_datasets)

    if not filtered_datasets:
        st.info("No datasets matched your search.")
        return

    cols = st.columns(4)
    for i, ds in enumerate(filtered_datasets):
        with cols[i % 4]:
            dataset_card(ds, "all")
