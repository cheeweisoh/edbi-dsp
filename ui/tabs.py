import streamlit as st
from services.dataset_service import search_datasets, get_visible_datasets
from ui.cards import dataset_card


def render_tabs() -> None:
    search = st.text_input("Search keywords")
    visible_datasets = get_visible_datasets()

    tabs = st.tabs(
        [
            "Popular",
            "All Products",
        ]
    )

    with tabs[0]:
        popular_datasets = search_datasets(
            search, category="Popular", datasets=visible_datasets
        )
        cols = st.columns(4)
        for i, ds in enumerate(popular_datasets):
            with cols[i % 4]:
                dataset_card(ds, "popular")

    with tabs[1]:
        all_datasets = search_datasets(search, datasets=visible_datasets)

        cols = st.columns(4)
        for i, ds in enumerate(all_datasets):
            with cols[i % 4]:
                dataset_card(ds, "all")
