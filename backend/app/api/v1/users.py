from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.user import UserResponse
from app.services.user_service import UserService
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/users", tags=["users"])


def _svc(db: AsyncSession = Depends(get_db)) -> UserService:
    return UserService(db)


@router.get("/", response_model=list[UserResponse])
async def list_users(_: User = Depends(get_current_user), svc: UserService = Depends(_svc)) -> list[UserResponse]:
    return await svc.list_users()
