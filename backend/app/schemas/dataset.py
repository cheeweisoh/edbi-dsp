from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class DatasetCreate(BaseModel):
    name: str
    description: str | None = None


class DatasetUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    is_active: bool | None = None


class DatasetResponse(BaseModel):
    id: UUID
    name: str
    description: str | None
    owner_id: UUID
    owner_name: str | None = None
    owner_email: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DatasetListResponse(BaseModel):
    id: UUID
    table_name: str
    display_name: str
    name: str
    description: str | None
    owner_id: UUID
    owner_name: str | None = None
    owner_email: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class DatasetMetadataUpsert(BaseModel):
    schema_name: str | None = None
    table_name: str | None = None
    source_system: str | None = None
    file_path: str | None = None
    row_count: int | None = None
    size_in_bytes: int | None = None
    last_refreshed: datetime | None = None
    metadata_json: dict | None = None


class DatasetMetadataResponse(BaseModel):
    dataset_id: UUID
    schema_name: str | None
    table_name: str | None
    source_system: str | None
    file_path: str | None
    row_count: int | None
    size_in_bytes: int | None
    last_refreshed: datetime | None
    metadata_json: dict | None
    owner_id: UUID | None = None
    owner_name: str | None = None
    owner_email: str | None = None

    model_config = {"from_attributes": True}
