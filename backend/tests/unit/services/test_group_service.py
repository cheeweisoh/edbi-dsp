import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.models.group import Group
from app.models.group_member import GroupMember
from app.models.user import User
from app.schemas.group import GroupCreate
from app.services.group_service import GroupService


def _make_user(**kwargs: object) -> User:
    defaults = dict(
        id=uuid.uuid4(),
        email="user@example.com",
        full_name="User",
        hashed_password="h",
        is_active=True,
        is_superuser=False,
    )
    return User(**{**defaults, **kwargs})


def _make_group(created_by: uuid.UUID, **kwargs: object) -> Group:
    defaults = dict(id=uuid.uuid4(), name="grp", description="desc", created_by=created_by)
    return Group(**{**defaults, **kwargs})


@pytest.fixture
def svc() -> GroupService:
    service = GroupService(MagicMock())
    service.repo = MagicMock()
    return service


class TestCreateAndGetGroup:
    async def test_create_group(self, svc: GroupService) -> None:
        user = _make_user()
        group = _make_group(created_by=user.id, name="analysts")
        svc.repo.create = AsyncMock(return_value=group)

        result = await svc.create_group(GroupCreate(name="analysts", description="a"), user)

        assert result == group
        svc.repo.create.assert_awaited_once_with(name="analysts", description="a", created_by=user.id)

    async def test_get_group_not_found(self, svc: GroupService) -> None:
        svc.repo.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(NotFoundError):
            await svc.get_group(uuid.uuid4())


class TestMembers:
    async def test_add_member_success(self, svc: GroupService) -> None:
        owner = _make_user()
        member_user_id = uuid.uuid4()
        group = _make_group(created_by=owner.id)
        member = GroupMember(group_id=group.id, user_id=member_user_id)
        svc.repo.get_by_id = AsyncMock(return_value=group)
        svc.repo.get_member = AsyncMock(return_value=None)
        svc.repo.add_member = AsyncMock(return_value=member)

        result = await svc.add_member(group.id, member_user_id, owner)

        assert result == member

    async def test_add_member_conflict(self, svc: GroupService) -> None:
        owner = _make_user()
        member_user_id = uuid.uuid4()
        group = _make_group(created_by=owner.id)
        existing = GroupMember(group_id=group.id, user_id=member_user_id)
        svc.repo.get_by_id = AsyncMock(return_value=group)
        svc.repo.get_member = AsyncMock(return_value=existing)

        with pytest.raises(ConflictError):
            await svc.add_member(group.id, member_user_id, owner)

    async def test_add_member_forbidden_for_non_admin(self, svc: GroupService) -> None:
        owner = _make_user()
        other = _make_user(id=uuid.uuid4(), email="other@example.com")
        group = _make_group(created_by=owner.id)
        svc.repo.get_by_id = AsyncMock(return_value=group)

        with pytest.raises(ForbiddenError):
            await svc.add_member(group.id, uuid.uuid4(), other)

    async def test_remove_member_not_found(self, svc: GroupService) -> None:
        owner = _make_user()
        group = _make_group(created_by=owner.id)
        svc.repo.get_by_id = AsyncMock(return_value=group)
        svc.repo.get_member = AsyncMock(return_value=None)

        with pytest.raises(NotFoundError):
            await svc.remove_member(group.id, uuid.uuid4(), owner)

    async def test_list_members(self, svc: GroupService) -> None:
        owner = _make_user()
        group = _make_group(created_by=owner.id)
        members = [GroupMember(group_id=group.id, user_id=uuid.uuid4())]
        svc.repo.get_by_id = AsyncMock(return_value=group)
        svc.repo.list_members = AsyncMock(return_value=members)

        result = await svc.list_members(group.id)

        assert result == members
