import base64
import binascii
import json

import streamlit as st
from services.group_service import GroupService


def _build_group_member_lookup(groups: list[dict], all_users: list[dict], group_service: GroupService) -> tuple[dict[str, list[dict]], dict[str, dict]]:
    users_by_id = {str(user["id"]): user for user in all_users}
    members_by_group_id: dict[str, list[dict]] = {}
    group_by_id = {str(group["id"]): group for group in groups}
    for group in groups:
        members_res = group_service.list_members(group["id"])
        if members_res.status_code != 200:
            continue
        members = members_res.json()
        members_by_group_id[str(group["id"])] = [users_by_id[str(member["user_id"])] for member in members if str(member["user_id"]) in users_by_id]
    return members_by_group_id, group_by_id


def _extract_current_user_id_from_token() -> str | None:
    token = st.session_state.get("access_token")
    if not token:
        return None

    segments = token.split(".")
    if len(segments) < 2:
        return None

    try:
        payload_segment = segments[1]
        padding = "=" * (-len(payload_segment) % 4)
        payload_bytes = base64.urlsafe_b64decode(payload_segment + padding)
        payload = json.loads(payload_bytes.decode("utf-8"))
    except binascii.Error, json.JSONDecodeError, UnicodeDecodeError:
        return None

    sub = payload.get("sub")
    return str(sub) if sub else None


def _reset_active_dialog() -> None:
    st.session_state.active_dialog = None
