import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dataset_permission import DatasetPermission, permissions_at_least


class PermissionRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def grant(self, dataset_id: uuid.UUID, grantee_type: str, grantee_id: uuid.UUID, permission: str, granted_by: uuid.UUID) -> DatasetPermission:
        """Upsert: one permission row per (dataset, grantee_type, grantee_id)."""
        result = await self.db.execute(
            select(DatasetPermission).where(
                DatasetPermission.dataset_id == dataset_id,
                DatasetPermission.grantee_type == grantee_type,
                DatasetPermission.grantee_id == grantee_id,
            )
        )
        perm = result.scalar_one_or_none()
        if perm is None:
            perm = DatasetPermission(
                dataset_id=dataset_id,
                grantee_type=grantee_type,
                grantee_id=grantee_id,
                permission=permission,
                granted_by=granted_by,
            )
            self.db.add(perm)
        else:
            perm.permission = permission
            perm.granted_by = granted_by
        await self.db.commit()
        await self.db.refresh(perm)
        return perm

    async def revoke(self, perm: DatasetPermission) -> None:
        await self.db.delete(perm)
        await self.db.commit()

    async def get_by_id(self, permission_id: uuid.UUID) -> DatasetPermission | None:
        result = await self.db.execute(select(DatasetPermission).where(DatasetPermission.id == permission_id))
        return result.scalar_one_or_none()

    async def list_for_dataset(self, dataset_id: uuid.UUID) -> list[DatasetPermission]:
        result = await self.db.execute(select(DatasetPermission).where(DatasetPermission.dataset_id == dataset_id))
        return list(result.scalars().all())

    async def get_accessible_dataset_ids(self, user_id: uuid.UUID, group_ids: list[uuid.UUID]) -> set[uuid.UUID]:
        result = await self.db.execute(
            select(DatasetPermission.dataset_id).where(
                DatasetPermission.grantee_type == "user",
                DatasetPermission.grantee_id == user_id,
            )
        )
        ids: set[uuid.UUID] = set(result.scalars().all())

        if group_ids:
            result = await self.db.execute(
                select(DatasetPermission.dataset_id).where(
                    DatasetPermission.grantee_type == "group",
                    DatasetPermission.grantee_id.in_(group_ids),
                )
            )
            ids.update(result.scalars().all())

        return ids

    async def check_access(self, dataset_id: uuid.UUID, user_id: uuid.UUID, group_ids: list[uuid.UUID], min_permission: str) -> bool:
        allowed = permissions_at_least(min_permission)

        result = await self.db.execute(
            select(DatasetPermission).where(
                DatasetPermission.dataset_id == dataset_id,
                DatasetPermission.grantee_type == "user",
                DatasetPermission.grantee_id == user_id,
                DatasetPermission.permission.in_(allowed),
            )
        )
        if result.scalar_one_or_none():
            return True

        if group_ids:
            result = await self.db.execute(
                select(DatasetPermission).where(
                    DatasetPermission.dataset_id == dataset_id,
                    DatasetPermission.grantee_type == "group",
                    DatasetPermission.grantee_id.in_(group_ids),
                    DatasetPermission.permission.in_(allowed),
                )
            )
            if result.scalar_one_or_none():
                return True

        return False
