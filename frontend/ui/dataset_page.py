import streamlit as st
import pandas as pd
from services.dataset_service import DatasetService
from services.query_service import QueryService


def apply_filters(df, filters):
    for col, value in filters.items():
        if isinstance(value, str) and value.strip() != "":
            df = df[df[col].astype(str).str.contains(value, case=False, na=False)]
        elif isinstance(value, tuple):
            min_val, max_val = value
            df = df[(df[col] >= min_val) & (df[col] <= max_val)]
        elif isinstance(value, list) and len(value) > 0:
            df = df[df[col].isin(value)]

    df.index = range(1, len(df) + 1)
    return df


def render_metadata_grid(items: list[tuple], cols_per_row: int = 4):
    for i in range(0, len(items), cols_per_row):
        row_items = items[i : i + cols_per_row]
        cols = st.columns(cols_per_row)

        for col, (label, value) in zip(cols, row_items):
            with col:
                st.markdown(
                    f"""
                    <div style = "
                        border: 1px solid #e5e7eb;
                        border-radiusL 8px;
                        padding: 12px;
                        min-height: 90px;
                    ">
                        <div style = "font-size: 12px; color: #6b7280;">
                            {label}
                        </div>
                        <div style = "font-size: 16px; font-weight: 600;">
                            {value}
                        </div>
                    </div>
                """,
                    unsafe_allow_html=True,
                )


def render_dataset_page():
    dataset_service = DatasetService(st.session_state.client)
    query_service = QueryService(st.session_state.client)

    curr_dataset = dataset_service.get(st.session_state.selected_dataset).json()
    curr_metadata = dataset_service.get_metadata(st.session_state.selected_dataset).json()

    if st.button("⬅ Back"):
        st.session_state.pop("selected_dataset")
        st.session_state.pop("filtered_df")
        st.rerun()

    st.markdown(f"## {curr_dataset['name']}")
    st.markdown(curr_dataset["description"])
    st.divider()

    col1, col2, col3 = st.columns([20, 1, 40])

    with col1:
        st.markdown("### Data Product Information")

        metadata_items = [
            ("Owner", curr_metadata["metadata_json"]["owner"]),
            ("Agency", curr_metadata["metadata_json"]["agency"]),
            ("Update Frequency", curr_metadata["metadata_json"]["update_frequency"]),
            ("Last Updated", curr_metadata["metadata_json"]["last_updated"]),
            ("Coverage Period", curr_metadata["metadata_json"]["coverage_period"]),
            ("Data Quality", curr_metadata["metadata_json"]["data_quality"]),
            ("Data Classification", curr_metadata["metadata_json"]["data_classification"]),
            ("Data Sharing Classification", curr_metadata["metadata_json"]["sharing_classification"]),
            ("Formats", ", ".join(curr_metadata["metadata_json"]["formats"])),
            ("Managed By", curr_dataset["owner_id"]),
        ]

        render_metadata_grid(metadata_items, 4)

        st.markdown("### Data Dictionary")

        data_dict_df = pd.DataFrame(curr_metadata["metadata_json"]["schema"])
        data_dict_df.rename(columns={"column": "Column Name", "type": "Data Type", "description": "Description"}, inplace=True)
        st.dataframe(data_dict_df, hide_index=True, width="stretch")

    with col3:
        st.markdown("### Data Preview")

        query_res = query_service.query(st.session_state.selected_dataset, limit=None).json()
        query_df = pd.DataFrame(query_res["rows"])
        if "filtered_df" not in st.session_state:
            st.session_state["filtered_df"] = query_df

        st.markdown("#### Select Columns")
        selected_columns = st.multiselect("Columns to include", query_res["columns"], default=query_res["columns"])

        st.markdown("#### Filters")
        filters = {}

        for col in selected_columns:
            col_dtype = query_df[col].dtype
            if pd.api.types.is_object_dtype(col_dtype) or pd.api.types.is_string_dtype(col_dtype):
                options = sorted(query_df[col].dropna().unique().tolist())
                filters[col] = st.multiselect(
                    f"{col} values",
                    options=options,
                    default=options,
                    key=f"filter_{col}",
                )
            elif pd.api.types.is_integer_dtype(col_dtype):
                min_val, max_val = int(query_df[col].min()), int(query_df[col].max())

                if min_val == max_val:
                    st.markdown(f"{col}: {min_val} (fixed)")
                    filters[col] = (min_val, max_val)
                else:
                    filters[col] = st.slider(
                        f"{col} range",
                        min_val,
                        max_val,
                        (min_val, max_val),
                        step=1,
                        key=f"filter_{col}",
                    )
            elif pd.api.types.is_float_dtype(col_dtype):
                min_val, max_val = float(query_df[col].min()), float(query_df[col].max())

                if min_val == max_val:
                    st.markdown(f"{col}: {min_val:.2f} (fixed)")
                    filters[col] = (min_val, max_val)
                else:
                    filters[col] = st.slider(
                        f"{col} range",
                        min_val,
                        max_val,
                        (min_val, max_val),
                        key=f"filter_{col}",
                    )

        with st.container(horizontal=True):
            if st.button("Generate Preview"):
                filtered_df = apply_filters(query_df[selected_columns], filters)
                st.session_state["filtered_df"] = filtered_df

            st.download_button(
                "Download Filtered Dataset (CSV)",
                st.session_state["filtered_df"].to_csv(index=False),
                file_name=f"{curr_dataset['name']}_filtered.csv",
                mime="text/csv",
            )

        st.divider()

        if "filtered_df" in st.session_state:
            st.markdown("#### Preview (Top 10 Rows)")
            st.dataframe(st.session_state["filtered_df"].head(10), width="stretch")
