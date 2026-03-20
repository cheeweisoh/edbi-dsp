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
    service.perm_svc.get_accessible_dataset_ids = AsyncMock(return_value=set())
    return service


class TestHelpers:
    def test_extract_sql_removes_code_fence(self) -> None:
        sql = QueryNLService._extract_sql("```sql\nSELECT * FROM electricity_sales\n```")
        assert sql == "SELECT * FROM electricity_sales"

    def test_extract_sql_normalizes_tokenizer_artifacts_and_missing_spaces(self) -> None:
        raw = "SELECTyear,month,consumption_m3ĠFROMwater_consumptionĠWHEREpremise_type='Residential'ĠANDyear=2020;"
        sql = QueryNLService._extract_sql(raw)
        assert sql == "SELECT year,month,consumption_m3 FROM water_consumption WHERE premise_type='Residential' AND year=2020;"

    def test_is_safe_sql(self) -> None:
        assert QueryNLService._is_safe_sql("SELECT * FROM t")
        assert not QueryNLService._is_safe_sql("DROP TABLE t")

    def test_is_allowed_sql(self) -> None:
        assert QueryNLService._is_allowed_sql("SELECT * FROM electricity_sales", ["electricity_sales"])
        assert not QueryNLService._is_allowed_sql("SELECT * FROM water_consumption", ["electricity_sales"])

    def test_build_schema_context_handles_multiple_datasets(self) -> None:
        context = QueryNLService._build_schema_context(
            [
                {
                    "name": "electricity_sales",
                    "metadata_json": {"description": "Electricity", "schema": [{"column": "year", "type": "INT"}]},
                },
                {
                    "name": "water_consumption",
                    "metadata_json": {"description": "Water", "schema": [{"column": "month", "type": "INT"}]},
                },
            ]
        )
        assert "Table: electricity_sales" in context
        assert "Table: water_consumption" in context


class TestGenerateSql:
    async def test_generate_sql_happy_path(self, svc: QueryNLService, monkeypatch: pytest.MonkeyPatch) -> None:
        user = _make_user()
        dataset = _make_dataset(owner_id=user.id, name="electricity_sales")
        metadata = DatasetMetadata(dataset_id=dataset.id, metadata_json={"description": "Monthly electricity sales", "schema": [{"column": "year", "type": "INT", "description": "year"}]})
        svc.dataset_repo.list_accessible = AsyncMock(return_value=[dataset])
        svc.perm_svc.get_accessible_dataset_ids = AsyncMock(return_value={dataset.id})
        svc.dataset_repo.get_metadata = AsyncMock(return_value=metadata)

        monkeypatch.setattr(
            QueryNLService,
            "_get_pipe",
            classmethod(lambda cls: lambda *args, **kwargs: [{"generated_text": "SELECT year FROM electricity_sales"}]),
        )

        sql = await svc.generate_sql("show years", user)

        assert sql == "SELECT year FROM electricity_sales"
        svc.perm_svc.get_accessible_dataset_ids.assert_awaited_once_with(user)

    async def test_generate_sql_raises_not_found_when_no_usable_metadata(self, svc: QueryNLService) -> None:
        user = _make_user()
        dataset = _make_dataset(owner_id=user.id)
        svc.dataset_repo.list_accessible = AsyncMock(return_value=[dataset])
        svc.perm_svc.get_accessible_dataset_ids = AsyncMock(return_value={dataset.id})
        svc.dataset_repo.get_metadata = AsyncMock(return_value=None)

        with pytest.raises(NotFoundError):
            await svc.generate_sql("q", user)

    async def test_generate_sql_superuser_reads_all_active(self, svc: QueryNLService, monkeypatch: pytest.MonkeyPatch) -> None:
        user = _make_user()
        user.is_superuser = True
        dataset = _make_dataset(owner_id=user.id, name="electricity_sales")
        svc.dataset_repo.list_active = AsyncMock(return_value=[dataset])
        svc.dataset_repo.get_metadata = AsyncMock(
            return_value=DatasetMetadata(
                dataset_id=dataset.id,
                metadata_json={"description": "x", "schema": [{"column": "year", "type": "INT"}]},
            )
        )
        monkeypatch.setattr(
            QueryNLService,
            "_get_pipe",
            classmethod(lambda cls: lambda *args, **kwargs: [{"generated_text": "SELECT year FROM electricity_sales"}]),
        )

        sql = await svc.generate_sql("q", user)

        assert sql == "SELECT year FROM electricity_sales"
        svc.dataset_repo.list_active.assert_awaited_once()

    async def test_generate_sql_raises_forbidden_for_unsafe_sql(
        self, svc: QueryNLService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        user = _make_user()
        dataset = _make_dataset(owner_id=user.id)
        metadata = DatasetMetadata(
            dataset_id=dataset.id,
            metadata_json={"description": "x", "schema": [{"column": "year", "type": "INT"}]},
        )
        svc.dataset_repo.list_accessible = AsyncMock(return_value=[dataset])
        svc.perm_svc.get_accessible_dataset_ids = AsyncMock(return_value={dataset.id})
        svc.dataset_repo.get_metadata = AsyncMock(return_value=metadata)
        monkeypatch.setattr(
            QueryNLService,
            "_get_pipe",
            classmethod(lambda cls: lambda *args, **kwargs: [{"generated_text": "DROP TABLE electricity_sales"}]),
        )

        with pytest.raises(ForbiddenError):
            await svc.generate_sql("drop it", user)

    async def test_generate_sql_raises_forbidden_for_unallowed_table(
        self, svc: QueryNLService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        user = _make_user()
        dataset = _make_dataset(owner_id=user.id)
        metadata = DatasetMetadata(
            dataset_id=dataset.id,
            metadata_json={"description": "x", "schema": [{"column": "year", "type": "INT"}]},
        )
        svc.dataset_repo.list_accessible = AsyncMock(return_value=[dataset])
        svc.perm_svc.get_accessible_dataset_ids = AsyncMock(return_value={dataset.id})
        svc.dataset_repo.get_metadata = AsyncMock(return_value=metadata)
        monkeypatch.setattr(
            QueryNLService,
            "_get_pipe",
            classmethod(lambda cls: lambda *args, **kwargs: [{"generated_text": "SELECT * FROM water_consumption"}]),
        )

        with pytest.raises(ForbiddenError):
            await svc.generate_sql("show all", user)
