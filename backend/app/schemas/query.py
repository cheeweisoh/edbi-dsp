from uuid import UUID

from pydantic import BaseModel


class DataQueryResponse(BaseModel):
    dataset_id: UUID
    file_path: str
    columns: list[str]
    rows: list[dict]
    row_count: int
    total_row_count: int


class QueryNLRequest(BaseModel):
    nl_query: str
    max_new_tokens: int = 500


class QueryNLResponse(BaseModel):
    sql: str
