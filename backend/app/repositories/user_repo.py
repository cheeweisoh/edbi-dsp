from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_active(self) -> list[User]:
        result = await self.db.execute(select(User).where(User.is_active.is_(True)).order_by(User.full_name, User.email))
        return list(result.scalars().all())

    async def get_by_id(self, user_id: object) -> User | None:
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()
