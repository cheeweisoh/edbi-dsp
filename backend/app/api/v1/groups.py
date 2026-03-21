import uuid

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.group import GroupCreate, GroupMemberResponse, GroupResponse
from app.services.group_service import GroupService
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/groups", tags=["groups"])


def _svc(db: AsyncSession = Depends(get_db)) -> GroupService:
    return GroupService(db)


@router.post("/", response_model=GroupResponse, status_code=status.HTTP_201_CREATED)
async def create_group(data: GroupCreate, current_user: User = Depends(get_current_user), svc: GroupService = Depends(_svc)) -> GroupResponse:
    return await svc.create_group(data, current_user)


@router.get("/", response_model=list[GroupResponse])
async def list_groups(current_user: User = Depends(get_current_user), svc: GroupService = Depends(_svc)) -> list[GroupResponse]:
    return await svc.list_groups(current_user)


@router.get("/{group_id}", response_model=GroupResponse)
async def get_group(group_id: uuid.UUID, _: User = Depends(get_current_user), svc: GroupService = Depends(_svc)) -> GroupResponse:
    return await svc.get_group(group_id)


@router.get("/{group_id}/members", response_model=list[GroupMemberResponse])
async def list_members(group_id: uuid.UUID, _: User = Depends(get_current_user), svc: GroupService = Depends(_svc)) -> list[GroupMemberResponse]:
    return await svc.list_members(group_id)


@router.put("/{group_id}/members/{user_id}", response_model=GroupMemberResponse, status_code=status.HTTP_201_CREATED)
async def add_member(group_id: uuid.UUID, user_id: uuid.UUID, current_user: User = Depends(get_current_user), svc: GroupService = Depends(_svc)) -> GroupMemberResponse:
    return await svc.add_member(group_id, user_id, current_user)


@router.delete("/{group_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(group_id: uuid.UUID, user_id: uuid.UUID, current_user: User = Depends(get_current_user), svc: GroupService = Depends(_svc)) -> None:
    await svc.remove_member(group_id, user_id, current_user)
