import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pandas as pd
import pytest

from app.exceptions import ForbiddenError, NotFoundError
from app.models.dataset import Dataset
from app.models.dataset_metadata import DatasetMetadata
from app.models.user import User
from app.services.query_service import QueryService


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


@pytest.fixture
def svc() -> QueryService:
    service = QueryService(MagicMock())
    service.dataset_repo = MagicMock()
    service.log_repo = MagicMock()
    service.perm_svc = MagicMock()
    service.perm_svc.verify_access = AsyncMock(return_value=None)
    service.log_repo.create = AsyncMock(return_value=None)
    return service


class TestReadDataset:
    async def test_raises_not_found_when_file_path_missing(self, svc: QueryService) -> None:
        dataset_id = uuid.uuid4()
        user = _make_user()
        svc.dataset_repo.get_metadata = AsyncMock(return_value=DatasetMetadata(dataset_id=dataset_id, file_path=None))

        with pytest.raises(NotFoundError):
            await svc.read_dataset(dataset_id, user)

    async def test_raises_not_found_when_file_missing(
        self, svc: QueryService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        dataset_id = uuid.uuid4()
        user = _make_user()
        dm = DatasetMetadata(dataset_id=dataset_id, file_path="missing.csv")
        svc.dataset_repo.get_metadata = AsyncMock(return_value=dm)
        monkeypatch.setattr(Path, "exists", lambda self: False)

        with pytest.raises(NotFoundError):
            await svc.read_dataset(dataset_id, user)

    async def test_returns_data_and_logs_query(
        self, svc: QueryService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        dataset_id = uuid.uuid4()
        user = _make_user()
        dm = DatasetMetadata(dataset_id=dataset_id, file_path="data/sample.csv")
        svc.dataset_repo.get_metadata = AsyncMock(return_value=dm)
        monkeypatch.setattr(Path, "exists", lambda self: True)

        df = pd.DataFrame(
            [
                {"year": 2024, "month": 1, "value": 10.5},
                {"year": 2024, "month": 2, "value": None},
                {"year": 2024, "month": 3, "value": 9.0},
            ]
        )
        monkeypatch.setattr("app.services.query_service.pd.read_csv", lambda path: df)

        result = await svc.read_dataset(dataset_id, user, limit=2, offset=1)

        assert result.dataset_id == dataset_id
        assert result.file_path == "data/sample.csv"
        assert result.columns == ["year", "month", "value"]
        assert result.row_count == 2
        assert result.total_row_count == 3
        assert result.rows[0]["month"] == 2
        assert result.rows[0]["value"] is None
        svc.log_repo.create.assert_awaited_once()


class TestExecuteSql:
    async def test_executes_sql_and_logs_query(
        self, svc: QueryService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        user = _make_user()
        dataset_id = uuid.uuid4()
        dataset = Dataset(
            id=dataset_id,
            name="electricity_sales",
            description="desc",
            owner_id=user.id,
            is_active=True,
        )
        metadata = DatasetMetadata(dataset_id=dataset_id, file_path="data/electricity_sales.csv")
        svc.dataset_repo.list_accessible = AsyncMock(return_value=[dataset])
        svc.dataset_repo.get_metadata = AsyncMock(return_value=metadata)
        svc.perm_svc.get_accessible_dataset_ids = AsyncMock(return_value={dataset_id})
        monkeypatch.setattr(Path, "exists", lambda self: True)
        monkeypatch.setattr(
            "app.services.query_service.pd.read_csv",
            lambda path: pd.DataFrame([{"year": 2024, "month": 1}, {"year": 2024, "month": 2}]),
        )

        result = await svc.execute_sql("SELECT year, month FROM electricity_sales", user, limit=1, offset=1)

        assert result.columns == ["year", "month"]
        assert result.row_count == 1
        assert result.rows == [{"year": 2024, "month": 2}]
        svc.log_repo.create.assert_awaited_once()

    async def test_blocks_unsafe_sql(self, svc: QueryService) -> None:
        user = _make_user()

        with pytest.raises(ForbiddenError):
            await svc.execute_sql("DROP TABLE electricity_sales", user)

    async def test_blocks_unallowed_tables(self, svc: QueryService) -> None:
        user = _make_user()
        dataset_id = uuid.uuid4()
        dataset = Dataset(
            id=dataset_id,
            name="electricity_sales",
            description="desc",
            owner_id=user.id,
            is_active=True,
        )
        metadata = DatasetMetadata(dataset_id=dataset_id, file_path="data/electricity_sales.csv")
        svc.dataset_repo.list_accessible = AsyncMock(return_value=[dataset])
        svc.dataset_repo.get_metadata = AsyncMock(return_value=metadata)
        svc.perm_svc.get_accessible_dataset_ids = AsyncMock(return_value={dataset_id})

        with pytest.raises(ForbiddenError):
            await svc.execute_sql("SELECT * FROM water_consumption", user)
