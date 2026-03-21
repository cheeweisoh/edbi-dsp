import pandas as pd
import streamlit as st
from services.group_service import GroupService
from services.user_service import UserService
from ui.catalog import render_catalog
from ui.query_nl import render_query_data
from ui.utils import _extract_current_user_id_from_token, _reset_active_dialog


def _display_api_error(prefix: str, response) -> None:
    detail = response.text
    try:
        body = response.json()
        detail = body.get("detail", response.text)
    except ValueError:
        pass
    st.error(f"{prefix}: {detail}")


@st.dialog("Manage Groups", width="large", on_dismiss=_reset_active_dialog)
def manage_groups_dialog() -> None:
    group_service = GroupService(st.session_state.client)
    user_service = UserService(st.session_state.client)
    current_user_id = _extract_current_user_id_from_token()

    groups_res = group_service.list()
    users_res = user_service.list()

    if groups_res.status_code != 200:
        _display_api_error("Unable to load groups", groups_res)
        return
    if users_res.status_code != 200:
        _display_api_error("Unable to load people", users_res)
        return

    all_groups = groups_res.json()
    all_users = users_res.json()
    st.caption("Only group owners can manage members in the UI right now.")
    st.markdown("### Groups")

    owner_map = {str(user["id"]): user for user in all_users}
    for group in all_groups:
        with st.expander(group["name"], expanded=False):
            if str(group.get("created_by")) != current_user_id:
                continue

            if group.get("description"):
                st.caption(group["description"])
            created_by = owner_map.get(str(group["created_by"]), {})
            if created_by:
                st.caption(f"Owner: {created_by.get('full_name')} ({created_by.get('email')})")

            members_res = group_service.list_members(group["id"])
            if members_res.status_code != 200:
                _display_api_error("Unable to load members", members_res)
                continue
            group_members = members_res.json()
            member_ids = {str(member["user_id"]) for member in group_members}

            existing_member_users = [owner_map.get(member_id) for member_id in member_ids if owner_map.get(member_id)]
            existing_member_users = sorted(existing_member_users, key=lambda user: (user["full_name"], user["email"]))

            st.markdown("**Existing members**")
            if existing_member_users:
                members_df = pd.DataFrame([{"Name": user["full_name"], "Email": user["email"]} for user in existing_member_users])
                st.dataframe(members_df, hide_index=True, use_container_width=True)
            else:
                st.info("No members in this group yet.")

            group_user_options = [user for user in all_users if str(user["id"]) != current_user_id and str(user["id"]) not in member_ids]
            group_user_options = sorted(group_user_options, key=lambda user: (user["full_name"], user["email"]))
            option_labels = [f"{user['full_name']} ({user['email']})" for user in group_user_options]
            label_to_id = {f"{user['full_name']} ({user['email']})": str(user["id"]) for user in group_user_options}

            selected_to_add = st.multiselect(
                "Add members",
                options=option_labels,
                key=f"group_add_select_{group['id']}",
                placeholder="Select people to add",
            )
            add_col, remove_col = st.columns([1, 1])
            with add_col:
                if st.button("Add selected", key=f"group_add_btn_{group['id']}", use_container_width=True):
                    if not selected_to_add:
                        st.warning("Select at least one person to add.")
                    else:
                        success_count = 0
                        for label in selected_to_add:
                            user_id = label_to_id[label]
                            if user_id in member_ids:
                                continue
                            add_res = group_service.add_member(group["id"], user_id)
                            if add_res.status_code == 201:
                                success_count += 1
                            elif add_res.status_code != 409:
                                _display_api_error("Failed to add member", add_res)
                                st.rerun()
                        if success_count:
                            st.success(f"Added {success_count} member(s).")
                        st.rerun()

            existing_member_labels = [f"{user['full_name']} ({user['email']})" for user in existing_member_users]
            selected_to_remove = st.multiselect(
                "Current members",
                options=existing_member_labels,
                key=f"group_remove_select_{group['id']}",
                placeholder="Select members to remove",
            )
            remove_map = {f"{user['full_name']} ({user['email']})": str(user["id"]) for user in existing_member_users}
            with remove_col:
                if st.button("Remove selected", key=f"group_remove_btn_{group['id']}", use_container_width=True):
                    if not selected_to_remove:
                        st.warning("Select at least one member to remove.")
                    else:
                        success_count = 0
                        for label in selected_to_remove:
                            user_id = remove_map[label]
                            remove_res = group_service.remove_member(group["id"], user_id)
                            if remove_res.status_code == 204:
                                success_count += 1
                            else:
                                _display_api_error("Failed to remove member", remove_res)
                                st.rerun()
                        if success_count:
                            st.success(f"Removed {success_count} member(s).")
                        st.rerun()

    st.divider()
    st.markdown("### Create New Group")
    with st.form("create_group_form", clear_on_submit=True):
        group_name = st.text_input("Group name", placeholder="e.g. Analytics Working Group")
        group_desc = st.text_area("Description", placeholder="What is this group for?", height=100)
        create_submitted = st.form_submit_button("Create group", use_container_width=True)
    if create_submitted:
        if not group_name.strip():
            st.error("Group name is required.")
        else:
            create_res = group_service.create({"name": group_name.strip(), "description": group_desc.strip() or None})
            if create_res.status_code == 201:
                st.success("Group created successfully.")
                st.rerun()
            else:
                _display_api_error("Failed to create group", create_res)


def render_header():
    header_left, header_right = st.columns([8, 2])

    with header_left:
        st.markdown(
            """
            <div class="dashboard-welcome">
            <h1>Data Sharing Platform</h1>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with header_right:
        st.markdown("<div style='margin-top: 1.5rem'></div>", unsafe_allow_html=True)
        with st.popover("Account"):
            if st.button("Manage Groups", key="manage_group_btn", use_container_width=True) or st.session_state.active_dialog == "manage_groups":
                st.session_state.active_dialog = "manage_groups"
                manage_groups_dialog()


def render_tabs():
    top_tabs = st.tabs(["Query Data", "All Products"])

    with top_tabs[0]:
        render_query_data()

    with top_tabs[1]:
        render_catalog()
