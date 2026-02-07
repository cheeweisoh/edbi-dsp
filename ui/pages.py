import streamlit as st
import pandas as pd
from services.dataset_service import get_dataset_by_id
from services.storage_service import load_dataset
from services.auth_service import can_user_access_dataset, get_current_user


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
    ds = get_dataset_by_id(st.session_state["selected_dataset"])

    user = get_current_user()
    if not can_user_access_dataset(user, ds):
        st.error("No Permission")
        st.stop()

    if st.button("⬅ Back"):
        st.session_state.pop("selected_dataset")
        st.rerun()

    st.markdown(f"## {ds['title']}")
    st.markdown(ds["description"])

    st.markdown("### Data Product Information")

    metadata_items = [
        ("Owner", ds["owner"]),
        ("Agency", ds["agency"]),
        ("Update Frequency", ds["update_frequency"]),
        ("Last Updated", ds["last_updated"]),
        ("Coverage Period", ds["coverage_period"]),
        ("Data Quality", ds["data_quality"]),
        ("Data Classification", ds["data_classification"]),
        ("Data Sharing Classification", ds["sharing_classification"]),
        ("Formats", ", ".join(ds["formats"])),
        ("Managed By", ds["managed_by"]),
    ]

    render_metadata_grid(metadata_items, 4)

    st.markdown("### Data Dictionary")
    st.dataframe(pd.DataFrame(ds["schema"]), hide_index=True, width="stretch")

    st.markdown("### Data Preview")

    df = load_dataset(ds)

    st.markdown("#### Select Columns")
    all_columns = list(df.columns)
    selected_columns = st.multiselect(
        "Columns to include", all_columns, default=all_columns
    )

    st.markdown("#### Filters")
    filters = {}

    for col in selected_columns:
        col_dtype = df[col].dtype
        if pd.api.types.is_object_dtype(col_dtype) or pd.api.types.is_string_dtype(
            col_dtype
        ):
            options = sorted(df[col].dropna().unique().tolist())
            filters[col] = st.multiselect(
                f"{col} values",
                options=options,
                default=options,
                key=f"filter_{col}",
            )
        elif pd.api.types.is_integer_dtype(col_dtype):
            min_val, max_val = int(df[col].min()), int(df[col].max())

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
            min_val, max_val = float(df[col].min()), float(df[col].max())

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

    if st.button("Generate Preview"):
        filtered_df = apply_filters(df[selected_columns], filters)
        st.session_state["filtered_df"] = filtered_df

    if "filtered_df" in st.session_state:
        st.markdown("#### Preview (Top 10 Rows)")
        st.dataframe(st.session_state["filtered_df"].head(10), width="stretch")

        st.markdown("### Download")

        st.download_button(
            "Download Filtered Dataset (CSV)",
            st.session_state["filtered_df"].to_csv(index=False),
            file_name=f"{ds['id']}_filtered.csv",
            mime="text/csv",
        )
