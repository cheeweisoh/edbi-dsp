import streamlit as st
from services.dataset_service import DatasetService


def _render_card_styles() -> None:
    st.markdown(
        """
        <style>
        div[data-testid="stVerticalBlock"] div.dataset-card {
            min-height: 160px;
            border: 1px solid rgba(148, 163, 184, 0.5);
            border-radius: 10px;
            padding: 10px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            box-sizing: border-box;
            background: var(--secondary-background-color);
        }
        div[data-testid="stVerticalBlock"] div.dataset-card-content {
            overflow: hidden;
        }
        div[data-testid="stVerticalBlock"] div.dataset-card-title {
            color: var(--text-color);
            font-size: 0.98rem;
            font-weight: 600;
            margin-bottom: 6px;
        }
        div[data-testid="stVerticalBlock"] div.dataset-card-description {
            color: var(--text-color);
            opacity: 0.95;
            display: -webkit-box;
            -webkit-line-clamp: 3;
            -webkit-box-orient: vertical;
            overflow: hidden;
            text-overflow: ellipsis;
            word-break: break-word;
            font-size: 0.88rem;
            line-height: 1.35;
        }
        div[data-testid="stVerticalBlock"] div.dataset-card-footer {
            color: var(--text-color);
            opacity: 0.85;
            font-size: 0.78rem;
            margin-top: 8px;
            padding-top: 6px;
            border-top: 1px solid rgba(148, 163, 184, 0.35);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def search_datasets(search: str, datasets: list[dict]) -> list[dict]:
    query = search.strip().lower()
    if not query:
        return datasets

    filtered: list[dict] = []
    for dataset in datasets:
        title = str(dataset.get("display_name") or dataset.get("name") or dataset.get("title") or "")
        description = str(dataset.get("description") or "")
        if query in title.lower() or query in description.lower():
            filtered.append(dataset)
    return filtered


def dataset_card(ds: dict, prefix: str | None) -> None:
    title = ds.get("display_name") or ds.get("name") or "Untitled Dataset"
    description = ds.get("description") or "No description provided."
    last_updated = ds.get("updated_at") or ds.get("last_updated") or "-"
    st.markdown(
        f"""
        <div class="dataset-card">
            <div class="dataset-card-content">
                <div class="dataset-card-title" style="font-size: 1.3rem;">{title}</div>
                <div class="dataset-card-description color: rgba(200, 200, 200);">{description}</div>
            </div>
            <div class="dataset-card-footer">Last updated: {last_updated}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("<div style='height: 2px;'></div>", unsafe_allow_html=True)
    if st.button("Learn more", key=f"{ds['id']}_{prefix}", use_container_width=True):
        st.session_state["selected_dataset"] = ds["id"]
        st.rerun()


def render_catalog() -> None:
    dataset_service = DatasetService(st.session_state.client)
    _render_card_styles()

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
