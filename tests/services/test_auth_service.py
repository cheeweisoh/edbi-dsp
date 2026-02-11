import types
import pytest

import services.auth_service as auth


@pytest.fixture(autouse=True)
def mock_streamlit_session_state(monkeypatch):
    fake_st = types.SimpleNamespace(session_state={})
    monkeypatch.setattr(auth, "st", fake_st)
    return fake_st.session_state


@pytest.fixture
def datasets():
    return [
        {"id": "public_ds", "visibility": "public", "required_tags": []},
        {"id": "internal_ds", "visibility": "internal", "required_tags": []},
        {"id": "finance_ds", "visibility": "internal", "required_tags": ["finance"]},
        {"id": "admin_ds", "visibility": "admin", "required_tags": []},
        {"id": "health_ds", "visibility": "admin", "required_tags": ["health"]},
    ]


def test_login_sets_user_in_session_state(mock_streamlit_session_state):
    auth.login("alice")

    user = auth.get_current_user()
    assert user == auth.USERS["alice"]


def test_login_unknown_user_sets_none(mock_streamlit_session_state):
    auth.login("unknown")

    user = auth.get_current_user()
    assert user is None


def test_get_current_user_when_not_logged_in(mock_streamlit_session_state):
    assert auth.get_current_user() is None


def test_access_denied_when_user_is_none(datasets):
    assert not auth.can_user_access_dataset(None, datasets[0])


def test_public_user_can_access_public_dataset():
    user = auth.USERS["alice"]
    dataset = {"visibility": "public", "required_tags": []}

    assert auth.can_user_access_dataset(user, dataset)


def test_public_user_cannot_access_internal_dataset():
    user = auth.USERS["alice"]
    dataset = {"visibility": "internal", "required_tags": []}

    assert not auth.can_user_access_dataset(user, dataset)


def test_internal_user_can_access_internal_dataset():
    user = auth.USERS["bob"]
    dataset = {"visibility": "internal", "required_tags": []}

    assert auth.can_user_access_dataset(user, dataset)


def test_internal_user_cannot_access_admin_dataset():
    user = auth.USERS["bob"]
    dataset = {"visibility": "admin", "required_tags": []}

    assert not auth.can_user_access_dataset(user, dataset)


def test_admin_user_can_access_all_roles():
    user = auth.USERS["admin"]

    assert auth.can_user_access_dataset(
        user, {"visibility": "public", "required_tags": []}
    )
    assert auth.can_user_access_dataset(
        user, {"visibility": "internal", "required_tags": []}
    )
    assert auth.can_user_access_dataset(
        user, {"visibility": "admin", "required_tags": []}
    )


def test_access_denied_when_missing_required_tags():
    user = auth.USERS["bob"]  # bob only has ["utilities"]
    dataset = {"visibility": "internal", "required_tags": ["finance"]}

    assert not auth.can_user_access_dataset(user, dataset)


def test_access_allowed_when_user_has_required_tags():
    user = auth.USERS["admin"]  # has utilities, finance, health
    dataset = {"visibility": "admin", "required_tags": ["finance", "health"]}

    assert auth.can_user_access_dataset(user, dataset)


def test_dataset_without_required_tags_defaults_to_allowed():
    user = auth.USERS["bob"]
    dataset = {"visibility": "internal"}

    assert auth.can_user_access_dataset(user, dataset)


def test_get_accessible_tables_for_public_user(datasets):
    user = auth.USERS["alice"]

    result = auth.get_accessible_tables(user, datasets)

    assert result == ["public_ds"]


def test_get_accessible_tables_for_internal_user(datasets):
    user = auth.USERS["bob"]

    result = auth.get_accessible_tables(user, datasets)

    assert set(result) == {"public_ds", "internal_ds"}


def test_get_accessible_tables_for_admin_user(datasets):
    user = auth.USERS["admin"]

    result = auth.get_accessible_tables(user, datasets)

    assert set(result) == {
        "public_ds",
        "internal_ds",
        "finance_ds",
        "admin_ds",
        "health_ds",
    }


def test_get_accessible_tables_with_no_user(datasets):
    result = auth.get_accessible_tables(None, datasets)

    assert result == []
