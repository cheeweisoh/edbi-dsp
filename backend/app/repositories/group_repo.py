import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.group import Group
from app.models.group_member import GroupMember


class GroupRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, name: str, description: str | None, created_by: uuid.UUID) -> Group:
        group = Group(name=name, description=description, created_by=created_by)
        self.db.add(group)
        await self.db.commit()
        await self.db.refresh(group)
        return group

    async def get_by_id(self, group_id: uuid.UUID) -> Group | None:
        result = await self.db.execute(select(Group).where(Group.id == group_id))
        return result.scalar_one_or_none()

    async def list_all(self) -> list[Group]:
        result = await self.db.execute(select(Group))
        return list(result.scalars().all())

    async def get_user_group_ids(self, user_id: uuid.UUID) -> list[uuid.UUID]:
        result = await self.db.execute(
            select(GroupMember.group_id).where(GroupMember.user_id == user_id)
        )
        return list(result.scalars().all())

    async def add_member(self, group_id: uuid.UUID, user_id: uuid.UUID) -> GroupMember:
        member = GroupMember(group_id=group_id, user_id=user_id)
        self.db.add(member)
        await self.db.commit()
        await self.db.refresh(member)
        return member

    async def get_member(self, group_id: uuid.UUID, user_id: uuid.UUID) -> GroupMember | None:
        result = await self.db.execute(
            select(GroupMember).where(
                GroupMember.group_id == group_id,
                GroupMember.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def remove_member(self, member: GroupMember) -> None:
        await self.db.delete(member)
        await self.db.commit()

    async def list_members(self, group_id: uuid.UUID) -> list[GroupMember]:
        result = await self.db.execute(
            select(GroupMember).where(GroupMember.group_id == group_id)
        )
        return list(result.scalars().all())
