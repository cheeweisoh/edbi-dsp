import re
import sqlite3
import time
import uuid
from pathlib import Path

import pandas as pd
from app.core.config import settings
from app.exceptions import AppError, ForbiddenError, NotFoundError
from app.models.user import User
from app.repositories.dataset_repo import DatasetRepository
from app.repositories.query_log_repo import QueryLogRepository
from app.schemas.query import DataQueryResponse, SQLQueryResponse
from app.services.gensql_service import GenSQLService
from app.services.permission_service import PermissionService
from sqlalchemy.ext.asyncio import AsyncSession


class QueryService:
    def __init__(self, db: AsyncSession) -> None:
        self.dataset_repo = DatasetRepository(db)
        self.log_repo = QueryLogRepository(db)
        self.perm_svc = PermissionService(db)

    async def read_dataset(self, dataset_id: uuid.UUID, current_user: User, limit: int | None = None, offset: int = 0) -> DataQueryResponse:
        await self.perm_svc.verify_access(current_user, dataset_id, min_permission="query")

        dm = await self.dataset_repo.get_metadata(dataset_id)
        if dm is None or not dm.file_path:
            raise NotFoundError(f"No file path configured for dataset {dataset_id}")

        file_path = Path(settings.FILE_BASE_DIR) / dm.file_path
        if not file_path.exists():
            raise NotFoundError(f"Data file not found: {dm.file_path}")

        t0 = time.monotonic()
        df = pd.read_csv(file_path)
        total_row_count = len(df)

        sliced = df.iloc[offset : (offset + limit) if limit is not None else None]
        normalized = sliced.astype(object).where(pd.notna(sliced), other=None)
        rows = normalized.to_dict(orient="records")
        elapsed_ms = int((time.monotonic() - t0) * 1000)

        await self.log_repo.create(
            user_id=current_user.id,
            dataset_id=dataset_id,
            executed_sql=f"READ CSV {dm.file_path}",
            execution_time_ms=elapsed_ms,
            row_count=len(rows),
        )

        return DataQueryResponse(
            dataset_id=dataset_id,
            file_path=dm.file_path,
            columns=list(df.columns),
            rows=rows,
            row_count=len(rows),
            total_row_count=total_row_count,
        )

    async def execute_sql(self, sql: str, current_user: User, limit: int | None = 500, offset: int = 0) -> SQLQueryResponse:
        normalized_sql = GenSQLService._extract_sql(sql)
        if not GenSQLService._is_safe_sql(normalized_sql):
            raise ForbiddenError("Unsafe SQL generated. Query blocked.")

        referenced_tables = self._extract_tables(normalized_sql)
        if not referenced_tables:
            raise ForbiddenError("You do not have access to any relevant datasets to generate this query.")

        datasets = await self._list_queryable_datasets(current_user)
        if not datasets:
            raise NotFoundError("No datasets with readable metadata are available for querying")

        allowed_tables = [name for name, _, _ in datasets]
        if not GenSQLService._is_allowed_sql(normalized_sql, allowed_tables):
            raise ForbiddenError("You are not allowed to access some tables in the query. Query blocked.")

        table_map = {name.lower(): (dataset_id, file_path) for name, dataset_id, file_path in datasets}
        selected_tables = [table for table in referenced_tables if table.lower() in table_map]
        if not selected_tables:
            raise ForbiddenError("SQL must reference at least one allowed dataset table.")

        db_conn = sqlite3.connect(":memory:")
        try:
            for table_name in selected_tables:
                dataset_id, csv_path = table_map[table_name.lower()]
                file_path = Path(settings.FILE_BASE_DIR) / csv_path
                if not file_path.exists():
                    raise NotFoundError(f"Data file not found: {csv_path}")
                pd.read_csv(file_path).to_sql(table_name, db_conn, index=False, if_exists="replace")

            t0 = time.monotonic()
            try:
                result_df = pd.read_sql_query(normalized_sql, db_conn)
            except Exception as exc:
                raise AppError(f"Invalid SQL query: {exc}", 400) from exc

            sliced = result_df.iloc[offset : (offset + limit) if limit is not None else None]
            normalized = sliced.astype(object).where(pd.notna(sliced), other=None)
            rows = normalized.to_dict(orient="records")
            elapsed_ms = int((time.monotonic() - t0) * 1000)

            first_dataset_id, _ = table_map[selected_tables[0].lower()]
            await self.log_repo.create(
                user_id=current_user.id,
                dataset_id=first_dataset_id,
                executed_sql=normalized_sql,
                execution_time_ms=elapsed_ms,
                row_count=len(rows),
            )

            return SQLQueryResponse(
                columns=list(result_df.columns),
                rows=rows,
                row_count=len(rows),
            )
        finally:
            db_conn.close()

    async def _list_queryable_datasets(self, current_user: User) -> list[tuple[str, uuid.UUID, str]]:
        if current_user.is_superuser:
            datasets = await self.dataset_repo.list_active()
        else:
            accessible_ids = await self.perm_svc.get_accessible_dataset_ids(current_user)
            datasets = await self.dataset_repo.list_accessible(current_user.id, accessible_ids)

        queryable: list[tuple[str, uuid.UUID, str]] = []
        for dataset in datasets:
            metadata = await self.dataset_repo.get_metadata(dataset.id)
            if metadata is None or not metadata.file_path:
                continue
            queryable.append((dataset.name, dataset.id, metadata.file_path))
        return queryable

    @staticmethod
    def _extract_tables(sql: str) -> list[str]:
        tables = re.findall(r"(?:from|join)\s+([a-zA-Z0-9_]+)", sql, flags=re.IGNORECASE)
        deduped: list[str] = []
        seen: set[str] = set()
        for table in tables:
            lowered = table.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            deduped.append(table)
        return deduped
