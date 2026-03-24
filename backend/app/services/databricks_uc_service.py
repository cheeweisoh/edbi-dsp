from typing import Any

from app.core.config import settings
from app.exceptions import AppError
from app.utils.datetime_utils import unix_to_minute_datetime
from databricks.sdk import WorkspaceClient


class DatabricksUnityCatalogService:
    def __init__(self) -> None:
        host = settings.DATABRICKS_HOST
        token = settings.DATABRICKS_TOKEN
        if not host or not token:
            raise AppError("Databricks host/token is not configured", 500)
        self.client = WorkspaceClient(host=host, token=token)

    async def list_tables(self, catalog_name: str, schema_name: str) -> list[dict[str, Any]]:
        if not catalog_name or not schema_name:
            raise AppError("Databricks Unity Catalog catalog/schema is not configured", 500)

        tables: list[dict[str, Any]] = []
        for table in self.client.tables.list(catalog_name=catalog_name, schema_name=schema_name):
            columns: list[dict[str, str | None]] = []
            for col in getattr(table, "columns", []) or []:
                columns.append(
                    {
                        "column": self._as_string(getattr(col, "name", None)),
                        "type": self._as_string(getattr(col, "type_text", None) or getattr(col, "type_name", None)),
                        "description": self._as_string(getattr(col, "comment", None)),
                    }
                )

            full_name = getattr(table, "full_name", None) or ".".join(
                [
                    getattr(table, "catalog_name", None) or catalog_name,
                    getattr(table, "schema_name", None) or schema_name,
                    getattr(table, "name", ""),
                ]
            )

            tables.append(
                {
                    "dataset_name": self._as_string(getattr(table, "name", None)),
                    "display_name": self._as_string(getattr(table, "name")).replace("_", " ").title(),
                    "catalog_name": self._as_string(getattr(table, "catalog_name", None)),
                    "schema_name": self._as_string(getattr(table, "schema_name", None)),
                    "full_name": self._as_string(full_name),
                    "description": self._as_string(getattr(table, "comment", None)),
                    "owner": self._as_string(getattr(table, "owner", None)),
                    "updated_by": self._as_string(getattr(table, "updated_by", None)),
                    "updated_at": unix_to_minute_datetime(getattr(table, "updated_at", None)),
                    "table_type": self._as_string(getattr(table, "table_type", None)),
                    "num_cols": self._as_string(getattr(getattr(table, "properties", None), "spark.sql.statistics.numRows", None)),
                    "columns": columns,
                }
            )
        return tables

    @staticmethod
    def _as_string(value: object) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            return value
        enum_value = getattr(value, "value", None)
        if isinstance(enum_value, str):
            return enum_value
        return str(value)
