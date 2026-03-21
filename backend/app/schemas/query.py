from uuid import UUID

from pydantic import BaseModel


class DataQueryResponse(BaseModel):
    dataset_id: UUID
    file_path: str
    columns: list[str]
    rows: list[dict]
    row_count: int
    total_row_count: int


class GenSQLRequest(BaseModel):
    nl_query: str
    max_new_tokens: int = 500


class GenSQLResponse(BaseModel):
    sql: str


class SQLQueryRequest(BaseModel):
    sql: str
    limit: int | None = 500
    offset: int = 0


class SQLQueryResponse(BaseModel):
    columns: list[str]
    rows: list[dict]
    row_count: int
