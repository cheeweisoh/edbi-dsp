import pandas as pd
import streamlit as st
from services.dataset_service import DatasetService
from services.query_service import QueryService


def _safe_json_or_error(response, context: str) -> dict | None:
    if response.status_code != 200:
        detail = response.text
        try:
            body = response.json()
            detail = body.get("detail", detail)
        except ValueError:
            pass
        st.error(f"{context}: {detail}")
        return None
    try:
        payload = response.json()
    except ValueError:
        st.error(f"{context}: Backend returned a non-JSON response.")
        return None
    if not isinstance(payload, dict):
        st.error(f"{context}: Unexpected response shape.")
        return None
    return payload


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

    curr_dataset = _safe_json_or_error(dataset_service.get(st.session_state.selected_dataset), "Failed to load dataset")
    if curr_dataset is None:
        return
    curr_metadata = _safe_json_or_error(dataset_service.get_metadata(st.session_state.selected_dataset), "Failed to load dataset metadata")
    if curr_metadata is None:
        return
    metadata_json = curr_metadata.get("metadata_json") if isinstance(curr_metadata, dict) else {}
    metadata_json = metadata_json if isinstance(metadata_json, dict) else {}
    schema_rows = metadata_json.get("schema")
    schema_rows = schema_rows if isinstance(schema_rows, list) else []

    if st.button("⬅ Back"):
        st.session_state.pop("selected_dataset")
        st.session_state.pop("filtered_df", None)
        st.rerun()

    st.markdown(f"## {curr_dataset.get('name') or 'Dataset'}")
    st.markdown(curr_dataset.get("description") or "No description provided.")
    st.divider()

    col1, col2, col3 = st.columns([20, 1, 40])

    with col1:
        st.markdown("### Data Product Information")

        metadata_items = [
            ("Owner", metadata_json.get("owner").split("@")[0]),
            ("Owner Email", metadata_json.get("owner") or "-"),
            ("Agency", metadata_json.get("agency") or "-"),
            ("Update Frequency", metadata_json.get("update_frequency") or "-"),
            ("Last Updated", metadata_json.get("updated_at") or metadata_json.get("last_updated") or str(curr_metadata.get("last_refreshed") or "-")),
            ("Coverage Period", metadata_json.get("coverage_period") or "-"),
            ("Data Quality", metadata_json.get("data_quality") or "-"),
            ("Data Classification", metadata_json.get("data_classification") or "-"),
            ("Data Sharing Classification", metadata_json.get("sharing_classification") or "-"),
            ("Formats", ", ".join(metadata_json.get("formats", [])) if isinstance(metadata_json.get("formats"), list) else "csv"),
            ("Managed By", metadata_json.get("updated_by") or "-"),
        ]

        render_metadata_grid(metadata_items, 2)

    with col3:
        st.markdown("### Data Dictionary")

        data_dict_df = pd.DataFrame(schema_rows)
        data_dict_df.rename(columns={"column": "Column Name", "type": "Data Type", "description": "Description"}, inplace=True)
        if not data_dict_df.empty:
            st.dataframe(data_dict_df, hide_index=True, width="stretch")
        else:
            st.info("No schema metadata available.")

    st.markdown("### Data Preview")

    query_res = _safe_json_or_error(query_service.query(st.session_state.selected_dataset, limit=None), "Failed to load dataset preview")
    if query_res is None:
        return
    result_columns = query_res.get("columns", [])
    result_rows = query_res.get("rows", [])

    query_df = pd.DataFrame(result_rows)
    if result_columns:
        query_df = query_df.reindex(columns=result_columns)

    if "filtered_df" not in st.session_state:
        st.session_state["filtered_df"] = query_df

    st.markdown("#### Select Columns")
    selected_columns = st.multiselect("Columns to include", result_columns, default=result_columns)

    st.markdown("#### Filters")
    filters = {}

    for col in selected_columns:
        if col not in query_df.columns:
            continue
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
            numeric_values = pd.to_numeric(query_df[col], errors="coerce").dropna()
            if numeric_values.empty:
                continue
            min_val, max_val = int(numeric_values.min()), int(numeric_values.max())

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
            numeric_values = pd.to_numeric(query_df[col], errors="coerce").dropna()
            if numeric_values.empty:
                continue
            min_val, max_val = float(numeric_values.min()), float(numeric_values.max())
            if not (pd.notna(min_val) and pd.notna(max_val)):
                continue

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
            selected_existing_columns = [col for col in selected_columns if col in query_df.columns]
            filtered_df = apply_filters(query_df[selected_existing_columns], filters)
            st.session_state["filtered_df"] = filtered_df

        st.download_button(
            "Download Filtered Dataset (CSV)",
            st.session_state["filtered_df"].to_csv(index=False),
            file_name=f"{(curr_dataset.get('name') or 'dataset').replace(' ', '_')}_filtered.csv",
            mime="text/csv",
        )

    st.divider()

    if "filtered_df" in st.session_state:
        st.markdown("#### Preview")
        st.dataframe(st.session_state["filtered_df"].head(10), width="stretch")
