import time
from typing import Any

from app.core.config import settings
from app.exceptions import AppError
from databricks import sql


class DatabricksSQLService:
    def __init__(self) -> None:
        self.host = settings.DATABRICKS_HOST
        self.token = settings.DATABRICKS_TOKEN
        self.http_path = settings.DATABRICKS_SQL_WAREHOUSE_HTTP_PATH
        if not self.host or not self.token or not self.http_path:
            raise AppError("Databricks SQL connection is not configured", 500)

    def execute_query(self, query: str) -> tuple[list[str], list[dict[str, Any]], int]:
        t0 = time.monotonic()
        with sql.connect(
            server_hostname=self.host,
            http_path=self.http_path,
            access_token=self.token,
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query)
                description = cursor.description or []
                columns = [col[0] for col in description]
                data = cursor.fetchall()
                rows = [dict(zip(columns, row)) for row in data]
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        return columns, rows, elapsed_ms

    def count_query(self, table_full_name: str) -> int:
        query = f"SELECT COUNT(*) AS total_row_count FROM {table_full_name}"
        columns, rows, _ = self.execute_query(query)
        if not rows or "total_row_count" not in rows[0]:
            raise AppError(f"Unable to count rows for table {table_full_name}", 500)
        _ = columns
        return int(rows[0]["total_row_count"])
