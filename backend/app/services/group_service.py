import uuid

from app.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.models.group import Group
from app.models.group_member import GroupMember
from app.models.user import User
from app.repositories.group_repo import GroupRepository
from app.schemas.group import GroupCreate
from sqlalchemy.ext.asyncio import AsyncSession


class GroupService:
    def __init__(self, db: AsyncSession) -> None:
        self.repo = GroupRepository(db)

    async def create_group(self, data: GroupCreate, current_user: User) -> Group:
        return await self.repo.create(
            name=data.name,
            description=data.description,
            created_by=current_user.id,
        )

    async def list_groups(self, current_user: User) -> list[Group]:
        if current_user.is_superuser:
            return await self.repo.list_all()
        return await self.repo.list_for_user(current_user.id)

    async def get_group(self, group_id: uuid.UUID) -> Group:
        group = await self.repo.get_by_id(group_id)
        if group is None:
            raise NotFoundError(f"Group {group_id} not found")
        return group

    async def add_member(self, group_id: uuid.UUID, user_id: uuid.UUID, current_user: User) -> GroupMember:
        group = await self.get_group(group_id)
        self._assert_group_admin(group, current_user)
        if await self.repo.get_member(group_id, user_id):
            raise ConflictError("User is already a member of this group")
        return await self.repo.add_member(group_id, user_id)

    async def remove_member(self, group_id: uuid.UUID, user_id: uuid.UUID, current_user: User) -> None:
        group = await self.get_group(group_id)
        self._assert_group_admin(group, current_user)
        member = await self.repo.get_member(group_id, user_id)
        if member is None:
            raise NotFoundError("User is not a member of this group")
        await self.repo.remove_member(member)

    async def list_members(self, group_id: uuid.UUID) -> list[GroupMember]:
        await self.get_group(group_id)
        return await self.repo.list_members(group_id)

    @staticmethod
    def _assert_group_admin(group: Group, user: User) -> None:
        if group.created_by != user.id and not user.is_superuser:
            raise ForbiddenError("Only the group owner or a superuser can manage members")
