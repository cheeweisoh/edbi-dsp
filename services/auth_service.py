import streamlit as st

USERS = {
    "alice": {"role": "public", "tags": []},
    "bob": {"role": "internal", "tags": ["utilities"]},
    "admin": {"role": "admin", "tags": ["utilities", "finance", "health"]},
}

ROLE_ORDER = {
    "public": 0,
    "internal": 1,
    "admin": 2,
}


def login(username: str):
    st.session_state["user"] = USERS.get(username)


def get_current_user():
    return st.session_state.get("user")


def can_user_access_dataset(user, dataset):
    if not user:
        return False

    user_role = ROLE_ORDER[user["role"]]
    dataset_role = ROLE_ORDER[dataset["visibility"]]

    if user_role < dataset_role:
        return False

    required_tags = set(dataset.get("required_tags", []))
    user_tags = set(user.get("tags", []))

    return required_tags.issubset(user_tags)


def get_accessible_tables(user, datasets):
    accessible = []
    for ds in datasets:
        if can_user_access_dataset(user, ds):
            accessible.append(ds["id"])
    return accessible
