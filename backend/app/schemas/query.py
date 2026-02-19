from uuid import UUID

from pydantic import BaseModel


class DataQueryResponse(BaseModel):
    dataset_id: UUID
    file_path: str
    columns: list[str]
    rows: list[dict]
    row_count: int
    total_row_count: int
