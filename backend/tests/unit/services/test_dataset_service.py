import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.models.dataset import Dataset
from app.models.dataset_metadata import DatasetMetadata
from app.models.user import User
from app.schemas.dataset import DatasetCreate, DatasetMetadataUpsert, DatasetUpdate
from app.services.dataset_service import DatasetService


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
        dataset_name="test_dataset",
        display_name="Test Dataset",
        description="desc",
        owner_id=owner_id,
        is_active=True,
    )
    return Dataset(**{**defaults, **kwargs})


@pytest.fixture
def svc() -> DatasetService:
    mock_db = MagicMock()
    service = DatasetService(mock_db)
    service.repo = MagicMock()
    service.perm_svc = MagicMock()
    service.perm_svc.verify_access = AsyncMock(return_value=None)
    service.perm_svc.get_accessible_dataset_ids = AsyncMock(return_value=set())
    return service


class TestCreateDataset:
    async def test_creates_successfully(self, svc: DatasetService) -> None:
        user = _make_user()
        data = DatasetCreate(name="New Dataset", description="desc")
        svc.repo.get_by_name = AsyncMock(return_value=None)
        expected = _make_dataset(owner_id=user.id, name="New Dataset")
        svc.repo.create = AsyncMock(return_value=expected)

        result = await svc.create_dataset(data, user)

        svc.repo.create.assert_awaited_once_with(
            name="New Dataset", description="desc", owner_id=user.id
        )
        assert result == expected

    async def test_raises_conflict_on_duplicate_name(self, svc: DatasetService) -> None:
        user = _make_user()
        data = DatasetCreate(name="Existing")
        svc.repo.get_by_name = AsyncMock(return_value=_make_dataset(owner_id=user.id))

        with pytest.raises(ConflictError):
            await svc.create_dataset(data, user)


class TestListDatasets:
    async def test_returns_active_datasets(self, svc: DatasetService) -> None:
        user = _make_user(is_superuser=True)
        datasets = [
            _make_dataset(owner_id=user.id),
            _make_dataset(owner_id=user.id, dataset_name="d2", display_name="D2"),
        ]
        svc.repo.list_active = AsyncMock(return_value=datasets)
        svc.repo.get_metadata = AsyncMock(return_value=None)

        result = await svc.list_datasets(user)

        assert result == datasets

    async def test_dedupes_by_uc_full_name_and_prefers_pretty_name(self, svc: DatasetService) -> None:
        user = _make_user(is_superuser=True)
        pretty = _make_dataset(owner_id=user.id, dataset_name="electricity_sales", display_name="Electricity Sales")
        raw = _make_dataset(owner_id=user.id, dataset_name="edbi_teamg01.gold.electricity_sales", display_name="Edbi Teamg01 Gold Electricity Sales")
        svc.repo.list_active = AsyncMock(return_value=[raw, pretty])
        svc.repo.get_metadata = AsyncMock(
            side_effect=[
                DatasetMetadata(dataset_id=raw.id, metadata_json={"unity_catalog": {"full_name": "cat.sch.electricity_sales"}}),
                DatasetMetadata(dataset_id=pretty.id, metadata_json={"unity_catalog": {"full_name": "cat.sch.electricity_sales"}}),
            ]
        )

        result = await svc.list_datasets(user)

        assert len(result) == 1
        assert result[0].display_name == "Electricity Sales"

    async def test_dedupes_snake_and_title_without_metadata(self, svc: DatasetService) -> None:
        user = _make_user(is_superuser=True)
        snake = _make_dataset(owner_id=user.id, dataset_name="case_offence_distribution", display_name="case_offence_distribution")
        title = _make_dataset(owner_id=user.id, dataset_name="Case Offence Distribution", display_name="Case Offence Distribution")
        svc.repo.list_active = AsyncMock(return_value=[snake, title])
        svc.repo.get_metadata = AsyncMock(return_value=None)

        result = await svc.list_datasets(user)

        assert len(result) == 1
        assert result[0].display_name == "Case Offence Distribution"


class TestGetDataset:
    async def test_returns_existing_dataset(self, svc: DatasetService) -> None:
        user = _make_user()
        dataset = _make_dataset(owner_id=user.id)
        svc.repo.get_by_id = AsyncMock(return_value=dataset)

        result = await svc.get_dataset(dataset.id, user)

        assert result == dataset

    async def test_raises_not_found_when_missing(self, svc: DatasetService) -> None:
        user = _make_user()
        svc.repo.get_by_id = AsyncMock(return_value=None)
        svc.perm_svc.verify_access = AsyncMock(side_effect=NotFoundError())

        with pytest.raises(NotFoundError):
            await svc.get_dataset(uuid.uuid4(), user)

    async def test_raises_not_found_when_inactive(self, svc: DatasetService) -> None:
        user = _make_user()
        dataset = _make_dataset(owner_id=user.id, is_active=False)
        svc.repo.get_by_id = AsyncMock(return_value=dataset)
        svc.perm_svc.verify_access = AsyncMock(side_effect=NotFoundError())

        with pytest.raises(NotFoundError):
            await svc.get_dataset(dataset.id, user)


class TestUpdateDataset:
    async def test_owner_can_update(self, svc: DatasetService) -> None:
        user = _make_user()
        dataset = _make_dataset(owner_id=user.id)
        svc.repo.get_by_id = AsyncMock(return_value=dataset)
        svc.repo.get_by_name = AsyncMock(return_value=None)
        updated = _make_dataset(owner_id=user.id, name="Updated")
        svc.repo.update = AsyncMock(return_value=updated)

        result = await svc.update_dataset(dataset.id, DatasetUpdate(name="Updated"), user)

        assert result == updated

    async def test_non_owner_raises_forbidden(self, svc: DatasetService) -> None:
        owner = _make_user()
        other = _make_user(id=uuid.uuid4(), email="other@example.com")
        dataset = _make_dataset(owner_id=owner.id)
        svc.repo.get_by_id = AsyncMock(return_value=dataset)

        with pytest.raises(ForbiddenError):
            await svc.update_dataset(dataset.id, DatasetUpdate(name="X"), other)

    async def test_superuser_can_update_any(self, svc: DatasetService) -> None:
        owner = _make_user()
        admin = _make_user(id=uuid.uuid4(), email="admin@example.com", is_superuser=True)
        dataset = _make_dataset(owner_id=owner.id)
        svc.repo.get_by_id = AsyncMock(return_value=dataset)
        svc.repo.get_by_name = AsyncMock(return_value=None)
        svc.repo.update = AsyncMock(return_value=dataset)

        await svc.update_dataset(dataset.id, DatasetUpdate(description="new desc"), admin)

        svc.repo.update.assert_awaited_once()


class TestDeleteDataset:
    async def test_owner_soft_deletes(self, svc: DatasetService) -> None:
        user = _make_user()
        dataset = _make_dataset(owner_id=user.id)
        svc.repo.get_by_id = AsyncMock(return_value=dataset)
        svc.repo.update = AsyncMock(return_value=dataset)

        await svc.delete_dataset(dataset.id, user)

        svc.repo.update.assert_awaited_once_with(dataset, is_active=False)

    async def test_non_owner_raises_forbidden(self, svc: DatasetService) -> None:
        owner = _make_user()
        other = _make_user(id=uuid.uuid4(), email="other@example.com")
        dataset = _make_dataset(owner_id=owner.id)
        svc.repo.get_by_id = AsyncMock(return_value=dataset)

        with pytest.raises(ForbiddenError):
            await svc.delete_dataset(dataset.id, other)


class TestGetMetadata:
    async def test_returns_metadata(self, svc: DatasetService) -> None:
        user = _make_user()
        dataset = _make_dataset(owner_id=user.id)
        dm = DatasetMetadata(dataset_id=dataset.id, schema_name="s", table_name="t")
        svc.repo.get_by_id = AsyncMock(return_value=dataset)
        svc.repo.get_metadata = AsyncMock(return_value=dm)

        result = await svc.get_metadata(dataset.id, user)

        assert result == dm

    async def test_raises_not_found_when_no_metadata(self, svc: DatasetService) -> None:
        user = _make_user()
        dataset = _make_dataset(owner_id=user.id)
        svc.repo.get_by_id = AsyncMock(return_value=dataset)
        svc.repo.get_metadata = AsyncMock(return_value=None)

        with pytest.raises(NotFoundError):
            await svc.get_metadata(dataset.id, user)


class TestUpsertMetadata:
    async def test_owner_can_upsert(self, svc: DatasetService) -> None:
        user = _make_user()
        dataset = _make_dataset(owner_id=user.id)
        dm = DatasetMetadata(dataset_id=dataset.id, schema_name="s")
        svc.repo.get_by_id = AsyncMock(return_value=dataset)
        svc.repo.upsert_metadata = AsyncMock(return_value=dm)

        data = DatasetMetadataUpsert(schema_name="s")
        result = await svc.upsert_metadata(dataset.id, data, user)

        assert result == dm

    async def test_non_owner_raises_forbidden(self, svc: DatasetService) -> None:
        owner = _make_user()
        other = _make_user(id=uuid.uuid4(), email="other@example.com")
        dataset = _make_dataset(owner_id=owner.id)
        svc.repo.get_by_id = AsyncMock(return_value=dataset)

        with pytest.raises(ForbiddenError):
            await svc.upsert_metadata(dataset.id, DatasetMetadataUpsert(), other)
