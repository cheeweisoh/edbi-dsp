import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import ForbiddenError, NotFoundError
from app.models.dataset_permission import DatasetPermission
from app.models.user import User
from app.repositories.dataset_repo import DatasetRepository
from app.repositories.group_repo import GroupRepository
from app.repositories.permission_repo import PermissionRepository
from app.schemas.permission import PermissionGrant


class PermissionService:
    def __init__(self, db: AsyncSession) -> None:
        self.dataset_repo = DatasetRepository(db)
        self.group_repo = GroupRepository(db)
        self.perm_repo = PermissionRepository(db)

    async def grant(
        self,
        dataset_id: uuid.UUID,
        data: PermissionGrant,
        current_user: User,
    ) -> DatasetPermission:
        dataset = await self.dataset_repo.get_by_id(dataset_id)
        if dataset is None or not dataset.is_active:
            raise NotFoundError(f"Dataset {dataset_id} not found")
        self._assert_owner_or_superuser(dataset, current_user)
        return await self.perm_repo.grant(
            dataset_id=dataset_id,
            grantee_type=data.grantee_type,
            grantee_id=data.grantee_id,
            permission=data.permission,
            granted_by=current_user.id,
        )

    async def revoke(
        self,
        dataset_id: uuid.UUID,
        permission_id: uuid.UUID,
        current_user: User,
    ) -> None:
        dataset = await self.dataset_repo.get_by_id(dataset_id)
        if dataset is None or not dataset.is_active:
            raise NotFoundError(f"Dataset {dataset_id} not found")
        self._assert_owner_or_superuser(dataset, current_user)
        perm = await self.perm_repo.get_by_id(permission_id)
        if perm is None or perm.dataset_id != dataset_id:
            raise NotFoundError(f"Permission {permission_id} not found")
        await self.perm_repo.revoke(perm)

    async def list_permissions(
        self, dataset_id: uuid.UUID, current_user: User
    ) -> list[DatasetPermission]:
        dataset = await self.dataset_repo.get_by_id(dataset_id)
        if dataset is None or not dataset.is_active:
            raise NotFoundError(f"Dataset {dataset_id} not found")
        self._assert_owner_or_superuser(dataset, current_user)
        return await self.perm_repo.list_for_dataset(dataset_id)

    async def verify_access(
        self,
        user: User,
        dataset_id: uuid.UUID,
        min_permission: str = "view",
    ) -> None:
        """Raise ForbiddenError if user does not have at least min_permission on this dataset."""
        dataset = await self.dataset_repo.get_by_id(dataset_id)
        if dataset is None or not dataset.is_active:
            raise NotFoundError(f"Dataset {dataset_id} not found")
        if user.is_superuser or dataset.owner_id == user.id:
            return
        group_ids = await self.group_repo.get_user_group_ids(user.id)
        if not await self.perm_repo.check_access(dataset_id, user.id, group_ids, min_permission):
            raise ForbiddenError("You do not have access to this dataset")

    async def get_accessible_dataset_ids(self, user: User) -> set[uuid.UUID]:
        """Return dataset IDs the user can access (via direct or group permissions)."""
        group_ids = await self.group_repo.get_user_group_ids(user.id)
        return await self.perm_repo.get_accessible_dataset_ids(user.id, group_ids)

    @staticmethod
    def _assert_owner_or_superuser(dataset: object, user: User) -> None:
        if getattr(dataset, "owner_id") != user.id and not user.is_superuser:
            raise ForbiddenError("Only the dataset owner or a superuser can manage permissions")
