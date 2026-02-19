from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

GranteeType = Literal["user", "group"]
PermissionLevel = Literal["view", "query", "edit", "admin"]


class PermissionGrant(BaseModel):
    grantee_type: GranteeType
    grantee_id: UUID
    permission: PermissionLevel


class PermissionResponse(BaseModel):
    id: UUID
    dataset_id: UUID
    grantee_type: str
    grantee_id: UUID
    permission: str
    granted_by: UUID
    granted_at: datetime

    model_config = {"from_attributes": True}
