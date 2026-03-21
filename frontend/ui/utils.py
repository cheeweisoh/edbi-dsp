import base64
import binascii
import json

import streamlit as st


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
