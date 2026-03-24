import uuid
from unittest.mock import AsyncMock, MagicMock

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
    service.databricks_sql = MagicMock()
    service.perm_svc.verify_access = AsyncMock(return_value=None)
    service.log_repo.create = AsyncMock(return_value=None)
    return service


class TestReadDataset:
    async def test_raises_not_found_when_uc_table_missing(self, svc: QueryService) -> None:
        dataset_id = uuid.uuid4()
        user = _make_user()
        svc.dataset_repo.get_metadata = AsyncMock(
            return_value=DatasetMetadata(dataset_id=dataset_id, metadata_json={})
        )

        with pytest.raises(NotFoundError):
            await svc.read_dataset(dataset_id, user)

    async def test_returns_data_and_logs_query(self, svc: QueryService) -> None:
        dataset_id = uuid.uuid4()
        user = _make_user()
        dm = DatasetMetadata(
            dataset_id=dataset_id,
            schema_name="analytics",
            table_name="sample",
            file_path="main.analytics.sample_from_path",
            metadata_json={"unity_catalog": {"full_name": "main.analytics.sample"}},
        )
        svc.dataset_repo.get_metadata = AsyncMock(return_value=dm)
        svc.databricks_sql.execute_query.return_value = (
            ["year", "month", "value"],
            [{"year": 2024, "month": 2, "value": None}, {"year": 2024, "month": 3, "value": 9.0}],
            12,
        )
        svc.databricks_sql.count_query.return_value = 3

        result = await svc.read_dataset(dataset_id, user, limit=2, offset=1)

        assert result.dataset_id == dataset_id
        assert result.file_path == "main.analytics.sample_from_path"
        assert result.columns == ["year", "month", "value"]
        assert result.row_count == 2
        assert result.total_row_count == 3
        assert result.rows[0]["month"] == 2
        assert result.rows[0]["value"] is None
        svc.databricks_sql.execute_query.assert_called_once_with(
            "SELECT * FROM main.analytics.sample_from_path LIMIT 2 OFFSET 1"
        )
        svc.log_repo.create.assert_awaited_once()


class TestExecuteSql:
    async def test_executes_sql_and_logs_query(self, svc: QueryService) -> None:
        user = _make_user()
        dataset_id = uuid.uuid4()
        dataset = Dataset(
            id=dataset_id,
            dataset_name="electricity_sales",
            display_name="Electricity Sales",
            description="desc",
            owner_id=user.id,
            is_active=True,
        )
        metadata = DatasetMetadata(
            dataset_id=dataset_id,
            schema_name="analytics",
            table_name="electricity_sales",
            file_path="main.analytics.electricity_sales",
            metadata_json={"unity_catalog": {"full_name": "main.analytics.electricity_sales"}},
        )
        svc.dataset_repo.list_accessible = AsyncMock(return_value=[dataset])
        svc.dataset_repo.get_metadata = AsyncMock(return_value=metadata)
        svc.perm_svc.get_accessible_dataset_ids = AsyncMock(return_value={dataset_id})
        svc.databricks_sql.execute_query.return_value = (
            ["year", "month"],
            [{"year": 2024, "month": 2}],
            10,
        )

        result = await svc.execute_sql("SELECT year, month FROM electricity_sales", user, limit=1, offset=1)

        assert result.columns == ["year", "month"]
        assert result.row_count == 1
        assert result.rows == [{"year": 2024, "month": 2}]
        svc.databricks_sql.execute_query.assert_called_once_with(
            "SELECT * FROM (SELECT year, month FROM main.analytics.electricity_sales) AS q LIMIT 1 OFFSET 1"
        )
        svc.log_repo.create.assert_awaited_once()

    async def test_executes_sql_with_trailing_semicolon(self, svc: QueryService) -> None:
        user = _make_user()
        dataset_id = uuid.uuid4()
        dataset = Dataset(
            id=dataset_id,
            dataset_name="case_officer_workload",
            display_name="Case Officer Workload",
            description="desc",
            owner_id=user.id,
            is_active=True,
        )
        metadata = DatasetMetadata(
            dataset_id=dataset_id,
            schema_name="gold",
            table_name="case_officer_workload",
            file_path="edbi_teamg01.gold.case_officer_workload",
            metadata_json={"unity_catalog": {"full_name": "edbi_teamg01.gold.case_officer_workload"}},
        )
        svc.dataset_repo.list_accessible = AsyncMock(return_value=[dataset])
        svc.dataset_repo.get_metadata = AsyncMock(return_value=metadata)
        svc.perm_svc.get_accessible_dataset_ids = AsyncMock(return_value={dataset_id})
        svc.databricks_sql.execute_query.return_value = (
            ["assigned_officer_name"],
            [{"assigned_officer_name": "Marcus Poh"}],
            10,
        )

        sql = (
            "SELECT assigned_officer_name FROM case_officer_workload "
            "WHERE assigned_officer_name = 'Marcus Poh';"
        )
        result = await svc.execute_sql(sql, user, limit=500, offset=0)

        assert result.row_count == 1
        svc.databricks_sql.execute_query.assert_called_once_with(
            "SELECT * FROM (SELECT assigned_officer_name FROM edbi_teamg01.gold.case_officer_workload "
            "WHERE assigned_officer_name = 'Marcus Poh') AS q LIMIT 500 OFFSET 0"
        )

    async def test_blocks_unsafe_sql(self, svc: QueryService) -> None:
        user = _make_user()

        with pytest.raises(ForbiddenError):
            await svc.execute_sql("DROP TABLE electricity_sales", user)

    async def test_blocks_unallowed_tables(self, svc: QueryService) -> None:
        user = _make_user()
        dataset_id = uuid.uuid4()
        dataset = Dataset(
            id=dataset_id,
            dataset_name="electricity_sales",
            display_name="Electricity Sales",
            description="desc",
            owner_id=user.id,
            is_active=True,
        )
        metadata = DatasetMetadata(
            dataset_id=dataset_id,
            schema_name="analytics",
            table_name="electricity_sales",
            file_path="main.analytics.electricity_sales",
            metadata_json={"unity_catalog": {"full_name": "main.analytics.electricity_sales"}},
        )
        svc.dataset_repo.list_accessible = AsyncMock(return_value=[dataset])
        svc.dataset_repo.get_metadata = AsyncMock(return_value=metadata)
        svc.perm_svc.get_accessible_dataset_ids = AsyncMock(return_value={dataset_id})

        with pytest.raises(ForbiddenError):
            await svc.execute_sql("SELECT * FROM water_consumption", user)

    async def test_superuser_can_query_non_allowlisted_table(self, svc: QueryService) -> None:
        admin = _make_user(is_superuser=True)
        dataset_id = uuid.uuid4()
        dataset = Dataset(
            id=dataset_id,
            dataset_name="electricity_sales",
            display_name="Electricity Sales",
            description="desc",
            owner_id=admin.id,
            is_active=True,
        )
        metadata = DatasetMetadata(
            dataset_id=dataset_id,
            schema_name="analytics",
            table_name="electricity_sales",
            file_path="main.analytics.electricity_sales",
            metadata_json={"unity_catalog": {"full_name": "main.analytics.electricity_sales"}},
        )
        svc.dataset_repo.list_active = AsyncMock(return_value=[dataset])
        svc.dataset_repo.get_metadata = AsyncMock(return_value=metadata)
        svc.databricks_sql.execute_query.return_value = (["c"], [{"c": 1}], 8)

        result = await svc.execute_sql("SELECT * FROM some_other_table", admin, limit=1, offset=0)

        assert result.row_count == 1
        svc.log_repo.create.assert_awaited_once()


class TestHelpers:
    def test_extract_tables_supports_qualified_names(self) -> None:
        sql = "SELECT * FROM main.analytics.electricity_sales e JOIN `main.analytics.water_consumption` w ON e.year = w.year"
        tables = QueryService._extract_tables(sql)
        assert tables == ["main.analytics.electricity_sales", "main.analytics.water_consumption"]

    def test_normalize_sql_strips_trailing_semicolon(self) -> None:
        normalized = QueryService._normalize_sql("SELECT * FROM t ;  ")
        assert normalized == "SELECT * FROM t "
