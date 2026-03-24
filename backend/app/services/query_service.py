import re
import uuid
from typing import Any

from app.core.config import settings
from app.exceptions import AppError, ForbiddenError, NotFoundError
from app.models.user import User
from app.repositories.dataset_repo import DatasetRepository
from app.repositories.query_log_repo import QueryLogRepository
from app.schemas.query import DataQueryResponse, SQLQueryResponse
from app.services.databricks_sql_service import DatabricksSQLService
from app.services.gensql_service import GenSQLService
from app.services.permission_service import PermissionService
from sqlalchemy.ext.asyncio import AsyncSession

TABLE_REF_PATTERN = r"(?:`[^`]+`|[a-zA-Z0-9_.]+)"
SQL_TABLE_CLAUSE_PATTERN = r"(?i)\b(from|join)\s+(.+?)(?=\s+(?:join|on|where|group|order|limit|offset|having|union)\b|,|\)|$)"


class QueryService:
    def __init__(self, db: AsyncSession) -> None:
        self.dataset_repo = DatasetRepository(db)
        self.log_repo = QueryLogRepository(db)
        self.perm_svc = PermissionService(db)
        self.databricks_sql: DatabricksSQLService | None = None

    async def read_dataset(self, dataset_id: uuid.UUID, current_user: User, limit: int | None = None, offset: int = 0) -> DataQueryResponse:
        await self.perm_svc.verify_access(current_user, dataset_id, min_permission="query")

        dm = await self.dataset_repo.get_metadata(dataset_id)
        table_ref = self._resolve_table_reference(
            dm.metadata_json if dm else None,
            dm.schema_name if dm else None,
            dm.table_name if dm else None,
            dm.file_path if dm else None,
            None,
        )
        if dm is None or table_ref is None:
            raise NotFoundError(f"No Unity Catalog table configured for dataset {dataset_id}")

        query = f"SELECT * FROM {table_ref}"
        if limit is not None:
            query += f" LIMIT {limit}"
        if offset > 0:
            query += f" OFFSET {offset}"
        databricks_sql = self._sql()
        columns, rows, elapsed_ms = databricks_sql.execute_query(query)
        total_row_count = databricks_sql.count_query(table_ref)

        await self.log_repo.create(
            user_id=current_user.id,
            dataset_id=dataset_id,
            executed_sql=query,
            execution_time_ms=elapsed_ms,
            row_count=len(rows),
        )

        return DataQueryResponse(
            dataset_id=dataset_id,
            file_path=table_ref,
            columns=columns,
            rows=rows,
            row_count=len(rows),
            total_row_count=total_row_count,
        )

    async def execute_sql(self, sql: str, current_user: User, limit: int | None = 500, offset: int = 0) -> SQLQueryResponse:
        normalized_sql = self._normalize_sql(sql)
        if not GenSQLService._is_safe_sql(normalized_sql):
            raise ForbiddenError("Unsafe SQL generated. Query blocked.")

        datasets = await self._list_queryable_datasets(current_user)
        if not datasets:
            raise NotFoundError("No datasets with readable metadata are available for querying")

        alias_to_table = self._build_alias_to_table_map(datasets)
        normalized_sql = self._qualify_sql_tables(normalized_sql, alias_to_table)

        referenced_tables = self._extract_tables(normalized_sql)
        if not referenced_tables:
            raise ForbiddenError("You do not have access to any relevant datasets to generate this query.")

        allowed_tables = [table_ref for _, _, table_ref in datasets]
        if not current_user.is_superuser and not GenSQLService._is_allowed_sql(normalized_sql, allowed_tables):
            raise ForbiddenError("You are not allowed to access some tables in the query. Query blocked.")

        table_map = {table_ref.lower(): (dataset_id, table_ref) for _, dataset_id, table_ref in datasets}
        selected_tables = [table for table in referenced_tables if table.lower() in table_map]
        if not current_user.is_superuser and not selected_tables:
            raise ForbiddenError("SQL must reference at least one allowed dataset table.")

        paginated_sql = normalized_sql
        if limit is not None or offset > 0:
            q_limit = "ALL" if limit is None else str(limit)
            paginated_sql = f"SELECT * FROM ({normalized_sql}) AS q LIMIT {q_limit} OFFSET {offset}"

        try:
            columns, rows, elapsed_ms = self._sql().execute_query(paginated_sql)
        except AppError:
            raise
        except Exception as exc:
            raise AppError(f"Invalid SQL query: {exc}", 400) from exc

        if selected_tables:
            first_dataset_id, _ = table_map[selected_tables[0].lower()]
        else:
            # Superusers can query broader tables; still log against a known dataset.
            _, first_dataset_id, _ = datasets[0]
        await self.log_repo.create(
            user_id=current_user.id,
            dataset_id=first_dataset_id,
            executed_sql=paginated_sql,
            execution_time_ms=elapsed_ms,
            row_count=len(rows),
        )

        return SQLQueryResponse(
            columns=columns,
            rows=rows,
            row_count=len(rows),
        )

    @staticmethod
    def _normalize_sql(sql: str) -> str:
        normalized = GenSQLService._extract_sql(sql).strip()
        return re.sub(r";+\s*$", "", normalized)

    async def _list_queryable_datasets(self, current_user: User) -> list[tuple[set[str], uuid.UUID, str]]:
        if current_user.is_superuser:
            datasets = await self.dataset_repo.list_active()
        else:
            accessible_ids = await self.perm_svc.get_accessible_dataset_ids(current_user)
            datasets = await self.dataset_repo.list_accessible(current_user.id, accessible_ids)

        queryable: list[tuple[set[str], uuid.UUID, str]] = []
        for dataset in datasets:
            metadata = await self.dataset_repo.get_metadata(dataset.id)
            table_ref = self._resolve_table_reference(
                metadata.metadata_json if metadata else None,
                metadata.schema_name if metadata else None,
                metadata.table_name if metadata else None,
                metadata.file_path if metadata else None,
                getattr(dataset, "dataset_name", None),
            )
            if metadata is None or table_ref is None:
                continue
            aliases = self._build_table_aliases(
                table_ref=table_ref,
                dataset_name=getattr(dataset, "dataset_name", None),
                display_name=getattr(dataset, "display_name", None),
                schema_name=metadata.schema_name,
                table_name=metadata.table_name,
            )
            queryable.append((aliases, dataset.id, table_ref))
        return queryable

    @staticmethod
    def _extract_tables(sql: str) -> list[str]:
        tables = re.findall(rf"(?:from|join)\s+({TABLE_REF_PATTERN})", sql, flags=re.IGNORECASE)
        deduped: list[str] = []
        seen: set[str] = set()
        for table in tables:
            normalized = table.replace("`", "").lower()
            lowered = normalized
            if lowered in seen:
                continue
            seen.add(lowered)
            deduped.append(table.replace("`", ""))
        return deduped

    @staticmethod
    def _normalize_identifier(value: str) -> str:
        return value.replace("`", "").replace('"', "").strip().lower()

    @staticmethod
    def _qualify_with_env(table_name: str) -> str:
        catalog = settings.DATABRICKS_UC_CATALOG
        schema = settings.DATABRICKS_UC_SCHEMA
        if catalog and schema:
            return f"{catalog}.{schema}.{table_name}"
        if schema:
            return f"{schema}.{table_name}"
        return table_name

    @classmethod
    def _resolve_table_reference(
        cls,
        metadata_json: dict[str, Any] | None,
        schema_name: str | None,
        table_name: str | None,
        file_path: str | None,
        dataset_name: str | None,
    ) -> str | None:
        if file_path and file_path.strip():
            return file_path
        if isinstance(metadata_json, dict):
            metadata_path = metadata_json.get("file_path")
            if isinstance(metadata_path, str) and metadata_path.strip():
                return metadata_path
            uc_info = metadata_json.get("unity_catalog")
            if isinstance(uc_info, dict):
                full_name = uc_info.get("full_name")
                if isinstance(full_name, str) and full_name.strip():
                    return full_name
        if table_name and table_name.strip():
            return cls._qualify_with_env(table_name)
        if dataset_name and dataset_name.strip():
            return cls._qualify_with_env(dataset_name)
        if schema_name and table_name:
            return f"{schema_name}.{table_name}"
        if table_name:
            return table_name
        if dataset_name:
            return dataset_name
        return None

    @classmethod
    def _build_table_aliases(
        cls,
        table_ref: str,
        dataset_name: str | None,
        display_name: str | None,
        schema_name: str | None,
        table_name: str | None,
    ) -> set[str]:
        aliases: set[str] = set()

        def add_alias(raw: str | None) -> None:
            if not isinstance(raw, str):
                return
            normalized = cls._normalize_identifier(raw)
            if not normalized:
                return
            aliases.add(normalized)
            parts = [part for part in normalized.split(".") if part]
            if parts:
                aliases.add(parts[-1])
            if len(parts) >= 2:
                aliases.add(".".join(parts[-2:]))

        add_alias(table_ref)
        add_alias(dataset_name)
        add_alias(table_name)
        if schema_name and table_name:
            add_alias(f"{schema_name}.{table_name}")
        if display_name:
            add_alias(display_name)
            add_alias(display_name.replace(" ", "_"))
        return aliases

    @staticmethod
    def _build_alias_to_table_map(datasets: list[tuple[set[str], uuid.UUID, str]]) -> dict[str, str]:
        alias_map: dict[str, str] = {}
        for aliases, _, table_ref in datasets:
            for alias in aliases:
                alias_map[alias] = table_ref
        return alias_map

    @classmethod
    def _qualify_sql_tables(cls, sql: str, alias_to_table: dict[str, str]) -> str:
        def qualify_candidate(raw_candidate: str) -> str:
            stripped = raw_candidate.strip()
            normalized = cls._normalize_identifier(stripped)
            if normalized in alias_to_table:
                return alias_to_table[normalized]

            tokens = stripped.split()
            for i in range(len(tokens), 0, -1):
                candidate = " ".join(tokens[:i])
                mapped = alias_to_table.get(cls._normalize_identifier(candidate))
                if not mapped:
                    continue
                suffix = " ".join(tokens[i:])
                return f"{mapped} {suffix}".strip()
            return stripped.replace("`", "")

        def repl(match: re.Match[str]) -> str:
            keyword = match.group(1)
            raw_candidate = match.group(2)
            return f"{keyword} {qualify_candidate(raw_candidate)}"

        return re.sub(SQL_TABLE_CLAUSE_PATTERN, repl, sql)

    def _sql(self) -> DatabricksSQLService:
        if self.databricks_sql is None:
            self.databricks_sql = DatabricksSQLService()
        return self.databricks_sql
