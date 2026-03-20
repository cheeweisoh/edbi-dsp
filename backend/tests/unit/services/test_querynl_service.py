import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.exceptions import ForbiddenError, NotFoundError
from app.models.dataset import Dataset
from app.models.dataset_metadata import DatasetMetadata
from app.models.user import User
from app.services.querynl_service import QueryNLService


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
    defaults = dict(id=uuid.uuid4(), name="electricity_sales", description="desc", owner_id=owner_id, is_active=True)
    return Dataset(**{**defaults, **kwargs})


@pytest.fixture
def svc() -> QueryNLService:
    service = QueryNLService(MagicMock())
    service.dataset_repo = MagicMock()
    service.perm_svc = MagicMock()
    service.perm_svc.verify_access = AsyncMock(return_value=None)
    return service


class TestHelpers:
    def test_extract_sql_removes_code_fence(self) -> None:
        sql = QueryNLService._extract_sql("```sql\nSELECT * FROM electricity_sales\n```")
        assert sql == "SELECT * FROM electricity_sales"

    def test_is_safe_sql(self) -> None:
        assert QueryNLService._is_safe_sql("SELECT * FROM t")
        assert not QueryNLService._is_safe_sql("DROP TABLE t")

    def test_is_allowed_sql(self) -> None:
        assert QueryNLService._is_allowed_sql("SELECT * FROM electricity_sales", ["electricity_sales"])
        assert not QueryNLService._is_allowed_sql("SELECT * FROM water_consumption", ["electricity_sales"])

    def test_build_schema_context_requires_schema(self) -> None:
        with pytest.raises(NotFoundError):
            QueryNLService._build_schema_context("electricity_sales", {"description": "x"})


class TestGenerateSql:
    async def test_generate_sql_happy_path(self, svc: QueryNLService, monkeypatch: pytest.MonkeyPatch) -> None:
        user = _make_user()
        dataset = _make_dataset(owner_id=user.id)
        metadata = DatasetMetadata(
            dataset_id=dataset.id,
            metadata_json={
                "description": "Monthly electricity sales",
                "schema": [{"column": "year", "type": "INT", "description": "year"}],
            },
        )
        svc.dataset_repo.get_by_id = AsyncMock(return_value=dataset)
        svc.dataset_repo.get_metadata = AsyncMock(return_value=metadata)

        monkeypatch.setattr(
            QueryNLService,
            "_get_pipe",
            classmethod(lambda cls: lambda *args, **kwargs: [{"generated_text": "SELECT year FROM electricity_sales"}]),
        )

        sql = await svc.generate_sql(dataset.id, "show years", user)

        assert sql == "SELECT year FROM electricity_sales"

    async def test_generate_sql_raises_not_found_when_dataset_missing(self, svc: QueryNLService) -> None:
        user = _make_user()
        svc.dataset_repo.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(NotFoundError):
            await svc.generate_sql(uuid.uuid4(), "q", user)

    async def test_generate_sql_raises_not_found_when_metadata_missing(self, svc: QueryNLService) -> None:
        user = _make_user()
        dataset = _make_dataset(owner_id=user.id)
        svc.dataset_repo.get_by_id = AsyncMock(return_value=dataset)
        svc.dataset_repo.get_metadata = AsyncMock(return_value=None)

        with pytest.raises(NotFoundError):
            await svc.generate_sql(dataset.id, "q", user)

    async def test_generate_sql_raises_forbidden_for_unsafe_sql(
        self, svc: QueryNLService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        user = _make_user()
        dataset = _make_dataset(owner_id=user.id)
        metadata = DatasetMetadata(
            dataset_id=dataset.id,
            metadata_json={"description": "x", "schema": [{"column": "year", "type": "INT"}]},
        )
        svc.dataset_repo.get_by_id = AsyncMock(return_value=dataset)
        svc.dataset_repo.get_metadata = AsyncMock(return_value=metadata)
        monkeypatch.setattr(
            QueryNLService,
            "_get_pipe",
            classmethod(lambda cls: lambda *args, **kwargs: [{"generated_text": "DROP TABLE electricity_sales"}]),
        )

        with pytest.raises(ForbiddenError):
            await svc.generate_sql(dataset.id, "drop it", user)

    async def test_generate_sql_raises_forbidden_for_unallowed_table(
        self, svc: QueryNLService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        user = _make_user()
        dataset = _make_dataset(owner_id=user.id)
        metadata = DatasetMetadata(
            dataset_id=dataset.id,
            metadata_json={"description": "x", "schema": [{"column": "year", "type": "INT"}]},
        )
        svc.dataset_repo.get_by_id = AsyncMock(return_value=dataset)
        svc.dataset_repo.get_metadata = AsyncMock(return_value=metadata)
        monkeypatch.setattr(
            QueryNLService,
            "_get_pipe",
            classmethod(lambda cls: lambda *args, **kwargs: [{"generated_text": "SELECT * FROM water_consumption"}]),
        )

        with pytest.raises(ForbiddenError):
            await svc.generate_sql(dataset.id, "show all", user)
