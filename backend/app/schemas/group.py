from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class GroupCreate(BaseModel):
    name: str
    description: str | None = None


class GroupResponse(BaseModel):
    id: UUID
    name: str
    description: str | None
    created_by: UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class GroupMemberAdd(BaseModel):
    user_id: UUID


class GroupMemberResponse(BaseModel):
    group_id: UUID
    user_id: UUID
    joined_at: datetime

    model_config = {"from_attributes": True}
