import uuid

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.permission import PermissionGrant, PermissionResponse
from app.services.permission_service import PermissionService
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/datasets", tags=["permissions"])


def _svc(db: AsyncSession = Depends(get_db)) -> PermissionService:
    return PermissionService(db)


@router.get("/{dataset_id}/permissions", response_model=list[PermissionResponse])
async def list_permissions(
    dataset_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    svc: PermissionService = Depends(_svc),
) -> list[PermissionResponse]:
    return await svc.list_permissions(dataset_id, current_user)


@router.post(
    "/{dataset_id}/permissions",
    response_model=PermissionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def grant_permission(
    dataset_id: uuid.UUID,
    data: PermissionGrant,
    current_user: User = Depends(get_current_user),
    svc: PermissionService = Depends(_svc),
) -> PermissionResponse:
    return await svc.grant(dataset_id, data, current_user)


@router.delete("/{dataset_id}/permissions/{permission_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_permission(
    dataset_id: uuid.UUID,
    permission_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    svc: PermissionService = Depends(_svc),
) -> None:
    await svc.revoke(dataset_id, permission_id, current_user)
