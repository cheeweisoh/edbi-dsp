from app.models.user import User
from app.repositories.user_repo import UserRepository
from sqlalchemy.ext.asyncio import AsyncSession


class UserService:
    def __init__(self, db: AsyncSession) -> None:
        self.repo = UserRepository(db)

    async def list_users(self) -> list[User]:
        return await self.repo.list_active()
