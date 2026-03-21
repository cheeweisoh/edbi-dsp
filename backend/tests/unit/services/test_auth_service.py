import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.exceptions import UnauthorizedError
from app.models.user import User
from app.services.auth_service import AuthService


def _make_user(**kwargs: object) -> User:
    defaults = dict(
        id=uuid.uuid4(),
        email="user@example.com",
        full_name="User",
        hashed_password="hashed",
        is_active=True,
        is_superuser=False,
    )
    return User(**{**defaults, **kwargs})


@pytest.fixture
def svc() -> AuthService:
    mock_db = MagicMock()
    service = AuthService(mock_db)
    service.db.execute = AsyncMock()
    return service


class TestAuthenticate:
    async def test_returns_access_token_for_valid_credentials(
        self, svc: AuthService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        user = _make_user()
        exec_result = MagicMock()
        exec_result.scalar_one_or_none.return_value = user
        svc.db.execute.return_value = exec_result

        monkeypatch.setattr("app.services.auth_service.verify_password", lambda plain, hashed: True)
        monkeypatch.setattr("app.services.auth_service.create_access_token", lambda subject: f"token-{subject}")

        token = await svc.authenticate(user.email, "correct-password")

        assert token == f"token-{user.id}"

    async def test_raises_unauthorized_when_user_not_found(self, svc: AuthService) -> None:
        exec_result = MagicMock()
        exec_result.scalar_one_or_none.return_value = None
        svc.db.execute.return_value = exec_result

        with pytest.raises(UnauthorizedError):
            await svc.authenticate("missing@example.com", "password")

    async def test_raises_unauthorized_when_user_inactive(
        self, svc: AuthService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        user = _make_user(is_active=False)
        exec_result = MagicMock()
        exec_result.scalar_one_or_none.return_value = user
        svc.db.execute.return_value = exec_result
        monkeypatch.setattr("app.services.auth_service.verify_password", lambda plain, hashed: True)

        with pytest.raises(UnauthorizedError):
            await svc.authenticate(user.email, "password")

    async def test_raises_unauthorized_when_password_invalid(
        self, svc: AuthService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        user = _make_user()
        exec_result = MagicMock()
        exec_result.scalar_one_or_none.return_value = user
        svc.db.execute.return_value = exec_result
        monkeypatch.setattr("app.services.auth_service.verify_password", lambda plain, hashed: False)

        with pytest.raises(UnauthorizedError):
            await svc.authenticate(user.email, "wrong-password")
