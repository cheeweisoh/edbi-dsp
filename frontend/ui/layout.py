import pandas as pd
import streamlit as st
from services.dataset_service import DatasetService
from services.group_service import GroupService
from services.permission_service import PermissionService
from services.user_service import UserService
from ui.catalog import render_catalog
from ui.query_nl import render_query_data
from ui.utils import (_build_group_member_lookup,
                      _extract_current_user_id_from_token,
                      _reset_active_dialog)


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
    st.caption("Select a group that you manage to manage access.")
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

            add_col, remove_col = st.columns([1, 1])
            with add_col:
                selected_to_add = st.multiselect(
                    "Add Members",
                    options=option_labels,
                    key=f"group_add_select_{group['id']}",
                    placeholder="Select user(s) to add",
                )

                if st.button("Add Selected User", key=f"group_add_btn_{group['id']}", use_container_width=True):
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
            with remove_col:
                selected_to_remove = st.multiselect(
                    "Current Members",
                    options=existing_member_labels,
                    key=f"group_remove_select_{group['id']}",
                    placeholder="Select member(s) to remove",
                )
                remove_map = {f"{user['full_name']} ({user['email']})": str(user["id"]) for user in existing_member_users}
                if st.button("Remove Selected User", key=f"group_remove_btn_{group['id']}", use_container_width=True):
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


@st.dialog("Manage Datasets", width="large", on_dismiss=_reset_active_dialog)
def manage_datasets_dialog() -> None:
    dataset_service = DatasetService(st.session_state.client)
    permission_service = PermissionService(st.session_state.client)
    group_service = GroupService(st.session_state.client)
    user_service = UserService(st.session_state.client)
    current_user_id = _extract_current_user_id_from_token()

    datasets_res = dataset_service.list()
    groups_res = group_service.list()
    users_res = user_service.list()

    if datasets_res.status_code != 200:
        _display_api_error("Unable to load datasets", datasets_res)
        return
    if groups_res.status_code != 200:
        _display_api_error("Unable to load groups", groups_res)
        return
    if users_res.status_code != 200:
        _display_api_error("Unable to load users", users_res)
        return

    datasets = datasets_res.json()
    groups = groups_res.json()
    all_users = users_res.json()
    users_by_id = {str(user["id"]): user for user in all_users}
    members_by_group_id, groups_by_id = _build_group_member_lookup(groups, all_users, group_service)
    current_user = users_by_id.get(current_user_id or "")
    is_superuser = bool(current_user and current_user.get("is_superuser"))

    st.caption("Select a dataset that you manage to modify access")
    st.markdown("### Datasets")

    managed_datasets = datasets if is_superuser else [dataset for dataset in datasets if str(dataset["owner_id"]) == current_user_id]
    for dataset in managed_datasets:
        with st.expander(dataset["name"], expanded=False):
            if dataset.get("description"):
                st.caption(dataset["description"])

            permissions_res = permission_service.list(dataset["id"])
            if permissions_res.status_code != 200:
                _display_api_error("Unable to load dataset access", permissions_res)
                continue
            permissions = permissions_res.json()
            direct_user_permissions = [perm for perm in permissions if perm["grantee_type"] == "user"]
            group_permissions = [perm for perm in permissions if perm["grantee_type"] == "group"]

            access_rows: list[dict[str, str]] = []
            for perm in direct_user_permissions:
                user = users_by_id.get(str(perm["grantee_id"]))
                if not user:
                    continue
                access_rows.append(
                    {
                        "Name": user["full_name"],
                        "Email": user["email"],
                        "Access Source": "User",
                        "Permission": perm["permission"],
                    }
                )
            for perm in group_permissions:
                group_id = str(perm["grantee_id"])
                group = groups_by_id.get(group_id)
                group_name = group["name"] if group else group_id
                members = members_by_group_id.get(group_id, [])
                for member in members:
                    access_rows.append(
                        {
                            "Name": member["full_name"],
                            "Email": member["email"],
                            "Access Source": f"Group: {group_name}",
                            "Permission": perm["permission"],
                        }
                    )

            st.markdown("**Users with access**")
            if access_rows:
                access_df = (
                    pd.DataFrame(access_rows)
                    .drop_duplicates()
                    .groupby(["Name", "Email"], as_index=False)
                    .agg({"Access Source": lambda x: ", ".join(sorted(set(x))), "Permission": lambda x: ", ".join(sorted(set(x)))})
                    .sort_values(by=["Name", "Email", "Access Source"])
                )
                st.dataframe(access_df, hide_index=True, use_container_width=True, on_select="ignore")
            else:
                st.info("No users currently have access to this dataset.")

            direct_user_ids = {str(perm["grantee_id"]) for perm in direct_user_permissions}
            available_users = sorted(
                [user for user in all_users if (str(user["id"]) not in direct_user_ids) and (str(user["id"]) != current_user_id)],
                key=lambda user: (user["full_name"], user["email"]),
            )
            available_user_labels = [f"{user['full_name']} ({user['email']})" for user in available_users]
            user_label_to_id = {f"{user['full_name']} ({user['email']})": str(user["id"]) for user in available_users}

            manage_user_col, manage_group_col = st.columns([1, 1])
            with manage_user_col:
                selected_users_to_add = st.multiselect(
                    "Add New Users",
                    options=available_user_labels,
                    key=f"dataset_add_users_{dataset['id']}",
                    placeholder="Select users to grant direct access",
                )

                if st.button("Add Selected Users", key=f"dataset_add_users_btn_{dataset['id']}", use_container_width=True):
                    if not selected_users_to_add:
                        st.warning("Select at least one user to add.")
                    else:
                        success_count = 0
                        for user_label in selected_users_to_add:
                            user_id = user_label_to_id[user_label]
                            grant_res = permission_service.grant(
                                dataset["id"],
                                {"grantee_type": "user", "grantee_id": user_id, "permission": "query"},
                            )
                            if grant_res.status_code in (200, 201):
                                success_count += 1
                            else:
                                _display_api_error("Failed to add user access", grant_res)
                                st.rerun()
                        if success_count:
                            st.success(f"Added {success_count} direct user permission(s).")
                        st.rerun()

                removable_users = sorted(
                    [users_by_id[user_id] for user_id in direct_user_ids if user_id in users_by_id],
                    key=lambda user: (user["full_name"], user["email"]),
                )
                removable_user_labels = [f"{user['full_name']} ({user['email']})" for user in removable_users]
                user_label_to_permission = {
                    f"{users_by_id[str(perm['grantee_id'])]['full_name']} ({users_by_id[str(perm['grantee_id'])]['email']})": perm
                    for perm in direct_user_permissions
                    if str(perm["grantee_id"]) in users_by_id
                }

                selected_users_to_remove = st.multiselect(
                    "Remove Existing Users",
                    options=removable_user_labels,
                    key=f"dataset_remove_users_{dataset['id']}",
                    placeholder="Select direct users to remove",
                )

                if st.button("Remove Selected Users", key=f"dataset_remove_users_btn_{dataset['id']}", use_container_width=True):
                    if not selected_users_to_remove:
                        st.warning("Select at least one direct user to remove.")
                    else:
                        success_count = 0
                        for user_label in selected_users_to_remove:
                            permission_id = user_label_to_permission[user_label]["id"]
                            revoke_res = permission_service.revoke(dataset["id"], permission_id)
                            if revoke_res.status_code == 204:
                                success_count += 1
                            else:
                                _display_api_error("Failed to remove user access", revoke_res)
                                st.rerun()
                        if success_count:
                            st.success(f"Removed {success_count} direct user permission(s).")
                        st.rerun()

            with manage_group_col:
                granted_group_ids = {str(perm["grantee_id"]) for perm in group_permissions}
                available_groups = sorted(
                    [group for group in groups if str(group["id"]) not in granted_group_ids],
                    key=lambda group: group["name"].lower(),
                )
                available_group_labels = [group["name"] for group in available_groups]
                group_name_to_id = {group["name"]: str(group["id"]) for group in available_groups}

                selected_groups_to_add = st.multiselect(
                    "Add New User Groups",
                    options=available_group_labels,
                    key=f"dataset_add_groups_{dataset['id']}",
                    placeholder="Select groups to grant access",
                )

                if st.button("Add Selected Groups", key=f"dataset_add_groups_btn_{dataset['id']}", use_container_width=True):
                    if not selected_groups_to_add:
                        st.warning("Select at least one group to add.")
                    else:
                        success_count = 0
                        for group_name in selected_groups_to_add:
                            group_id = group_name_to_id[group_name]
                            grant_res = permission_service.grant(
                                dataset["id"],
                                {"grantee_type": "group", "grantee_id": group_id, "permission": "query"},
                            )
                            if grant_res.status_code in (200, 201):
                                success_count += 1
                            else:
                                _display_api_error("Failed to add group access", grant_res)
                                st.rerun()
                        if success_count:
                            st.success(f"Added {success_count} group access permission(s).")
                        st.rerun()

                removable_groups = sorted(
                    [groups_by_id[group_id] for group_id in granted_group_ids if group_id in groups_by_id],
                    key=lambda group: group["name"].lower(),
                )
                removable_group_labels = [group["name"] for group in removable_groups]
                group_name_to_permission = {groups_by_id[str(perm["grantee_id"])]["name"]: perm for perm in group_permissions if str(perm["grantee_id"]) in groups_by_id}

                selected_groups_to_remove = st.multiselect(
                    "Remove Existing User Groups",
                    options=removable_group_labels,
                    key=f"dataset_remove_groups_{dataset['id']}",
                    placeholder="Select groups to remove",
                )

                if st.button("Remove Selected Groups", key=f"dataset_remove_groups_btn_{dataset['id']}", use_container_width=True):
                    if not selected_groups_to_remove:
                        st.warning("Select at least one group to remove.")
                    else:
                        success_count = 0
                        for group_name in selected_groups_to_remove:
                            permission_id = group_name_to_permission[group_name]["id"]
                            revoke_res = permission_service.revoke(dataset["id"], permission_id)
                            if revoke_res.status_code == 204:
                                success_count += 1
                            else:
                                _display_api_error("Failed to remove group access", revoke_res)
                                st.rerun()
                        if success_count:
                            st.success(f"Removed {success_count} group access permission(s).")
                        st.rerun()

    if not managed_datasets:
        st.info("You do not own any datasets yet.")


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
            if st.button("Manage Datasets", key="manage_dataset_btn", use_container_width=True) or st.session_state.active_dialog == "manage_datasets":
                st.session_state.active_dialog = "manage_datasets"
                manage_datasets_dialog()


def render_tabs():
    top_tabs = st.tabs(["Query Data", "All Products"])

    with top_tabs[0]:
        render_query_data()

    with top_tabs[1]:
        render_catalog()
