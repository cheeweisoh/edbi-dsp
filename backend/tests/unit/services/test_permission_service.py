import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.exceptions import ForbiddenError, NotFoundError
from app.models.dataset import Dataset
from app.models.dataset_permission import DatasetPermission
from app.models.user import User
from app.schemas.permission import PermissionGrant
from app.services.permission_service import PermissionService


def _make_user(**kwargs: object) -> User:
    defaults = dict(
        id=uuid.uuid4(),
        email="user@example.com",
        full_name="User",
        hashed_password="h",
        is_active=True,
        is_superuser=False,
    )
    return User(**{**defaults, **kwargs})


def _make_dataset(owner_id: uuid.UUID, **kwargs: object) -> Dataset:
    defaults = dict(
        id=uuid.uuid4(),
        name="dataset",
        description="desc",
        owner_id=owner_id,
        is_active=True,
    )
    return Dataset(**{**defaults, **kwargs})


@pytest.fixture
def svc() -> PermissionService:
    service = PermissionService(MagicMock())
    service.dataset_repo = MagicMock()
    service.group_repo = MagicMock()
    service.perm_repo = MagicMock()
    return service


class TestGrantAndRevoke:
    async def test_grant_success(self, svc: PermissionService) -> None:
        owner = _make_user()
        dataset = _make_dataset(owner_id=owner.id)
        grant_data = PermissionGrant(grantee_type="user", grantee_id=uuid.uuid4(), permission="query")
        permission = DatasetPermission(
            dataset_id=dataset.id,
            grantee_type="user",
            grantee_id=grant_data.grantee_id,
            permission="query",
            granted_by=owner.id,
        )
        svc.dataset_repo.get_by_id = AsyncMock(return_value=dataset)
        svc.perm_repo.grant = AsyncMock(return_value=permission)

        result = await svc.grant(dataset.id, grant_data, owner)

        assert result == permission

    async def test_grant_not_found_for_missing_dataset(self, svc: PermissionService) -> None:
        owner = _make_user()
        svc.dataset_repo.get_by_id = AsyncMock(return_value=None)
        data = PermissionGrant(grantee_type="user", grantee_id=uuid.uuid4(), permission="view")

        with pytest.raises(NotFoundError):
            await svc.grant(uuid.uuid4(), data, owner)

    async def test_revoke_not_found_for_wrong_permission_dataset(self, svc: PermissionService) -> None:
        owner = _make_user()
        dataset = _make_dataset(owner_id=owner.id)
        permission_id = uuid.uuid4()
        other_dataset_permission = DatasetPermission(
            id=permission_id,
            dataset_id=uuid.uuid4(),
            grantee_type="user",
            grantee_id=uuid.uuid4(),
            permission="view",
            granted_by=owner.id,
        )
        svc.dataset_repo.get_by_id = AsyncMock(return_value=dataset)
        svc.perm_repo.get_by_id = AsyncMock(return_value=other_dataset_permission)

        with pytest.raises(NotFoundError):
            await svc.revoke(dataset.id, permission_id, owner)


class TestVerifyAccess:
    async def test_verify_access_allows_superuser(self, svc: PermissionService) -> None:
        user = _make_user(is_superuser=True)
        dataset = _make_dataset(owner_id=uuid.uuid4())
        svc.dataset_repo.get_by_id = AsyncMock(return_value=dataset)

        await svc.verify_access(user, dataset.id, min_permission="query")

    async def test_verify_access_allows_owner(self, svc: PermissionService) -> None:
        user = _make_user()
        dataset = _make_dataset(owner_id=user.id)
        svc.dataset_repo.get_by_id = AsyncMock(return_value=dataset)

        await svc.verify_access(user, dataset.id)

    async def test_verify_access_forbidden_without_permission(self, svc: PermissionService) -> None:
        user = _make_user()
        dataset = _make_dataset(owner_id=uuid.uuid4())
        svc.dataset_repo.get_by_id = AsyncMock(return_value=dataset)
        svc.group_repo.get_user_group_ids = AsyncMock(return_value=[uuid.uuid4()])
        svc.perm_repo.check_access = AsyncMock(return_value=False)

        with pytest.raises(ForbiddenError):
            await svc.verify_access(user, dataset.id, min_permission="query")

    async def test_verify_access_not_found_for_inactive_dataset(self, svc: PermissionService) -> None:
        user = _make_user()
        dataset = _make_dataset(owner_id=user.id, is_active=False)
        svc.dataset_repo.get_by_id = AsyncMock(return_value=dataset)

        with pytest.raises(NotFoundError):
            await svc.verify_access(user, dataset.id)


class TestAccessibleDatasetIds:
    async def test_get_accessible_dataset_ids(self, svc: PermissionService) -> None:
        user = _make_user()
        ids = {uuid.uuid4(), uuid.uuid4()}
        group_ids = [uuid.uuid4()]
        svc.group_repo.get_user_group_ids = AsyncMock(return_value=group_ids)
        svc.perm_repo.get_accessible_dataset_ids = AsyncMock(return_value=ids)

        result = await svc.get_accessible_dataset_ids(user)

        assert result == ids
