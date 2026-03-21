from app.core.security import create_access_token, verify_password
from app.exceptions import UnauthorizedError
from app.models.user import User
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def authenticate(self, email: str, password: str) -> str:
        result = await self.db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if user is None or not user.is_active or not verify_password(password, user.hashed_password):
            raise UnauthorizedError("Invalid credentials")
        return create_access_token(subject=str(user.id))
