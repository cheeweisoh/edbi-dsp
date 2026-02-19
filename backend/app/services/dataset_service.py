import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.models.dataset import Dataset
from app.models.dataset_metadata import DatasetMetadata
from app.models.user import User
from app.repositories.dataset_repo import DatasetRepository
from app.schemas.dataset import DatasetCreate, DatasetMetadataUpsert, DatasetUpdate
from app.services.permission_service import PermissionService


class DatasetService:
    def __init__(self, db: AsyncSession) -> None:
        self.repo = DatasetRepository(db)
        self.perm_svc = PermissionService(db)

    async def create_dataset(self, data: DatasetCreate, current_user: User) -> Dataset:
        if await self.repo.get_by_name(data.name):
            raise ConflictError(f"Dataset '{data.name}' already exists")
        return await self.repo.create(
            name=data.name,
            description=data.description,
            owner_id=current_user.id,
        )

    async def list_datasets(self, current_user: User) -> list[Dataset]:
        if current_user.is_superuser:
            return await self.repo.list_active()
        accessible_ids = await self.perm_svc.get_accessible_dataset_ids(current_user)
        return await self.repo.list_accessible(current_user.id, accessible_ids)

    async def get_dataset(self, dataset_id: uuid.UUID, current_user: User) -> Dataset:
        await self.perm_svc.verify_access(current_user, dataset_id, min_permission="view")
        dataset = await self.repo.get_by_id(dataset_id)
        if dataset is None or not dataset.is_active:
            raise NotFoundError(f"Dataset {dataset_id} not found")
        return dataset

    async def update_dataset(self, dataset_id: uuid.UUID, data: DatasetUpdate, current_user: User) -> Dataset:
        dataset = await self.repo.get_by_id(dataset_id)
        if dataset is None or not dataset.is_active:
            raise NotFoundError(f"Dataset {dataset_id} not found")
        self._assert_owner_or_superuser(dataset, current_user)
        updates = data.model_dump(exclude_unset=True)
        if "name" in updates:
            existing = await self.repo.get_by_name(updates["name"])
            if existing and existing.id != dataset_id:
                raise ConflictError(f"Dataset name '{updates['name']}' is already taken")
        return await self.repo.update(dataset, **updates)

    async def delete_dataset(self, dataset_id: uuid.UUID, current_user: User) -> None:
        dataset = await self.repo.get_by_id(dataset_id)
        if dataset is None or not dataset.is_active:
            raise NotFoundError(f"Dataset {dataset_id} not found")
        self._assert_owner_or_superuser(dataset, current_user)
        await self.repo.update(dataset, is_active=False)

    async def get_metadata(self, dataset_id: uuid.UUID, current_user: User) -> DatasetMetadata:
        await self.perm_svc.verify_access(current_user, dataset_id, min_permission="view")
        dm = await self.repo.get_metadata(dataset_id)
        if dm is None:
            raise NotFoundError(f"No metadata found for dataset {dataset_id}")
        return dm

    async def upsert_metadata(self, dataset_id: uuid.UUID, data: DatasetMetadataUpsert, current_user: User) -> DatasetMetadata:
        dataset = await self.repo.get_by_id(dataset_id)
        if dataset is None or not dataset.is_active:
            raise NotFoundError(f"Dataset {dataset_id} not found")
        self._assert_owner_or_superuser(dataset, current_user)
        return await self.repo.upsert_metadata(dataset_id, **data.model_dump(exclude_unset=True))

    @staticmethod
    def _assert_owner_or_superuser(dataset: Dataset, user: User) -> None:
        if dataset.owner_id != user.id and not user.is_superuser:
            raise ForbiddenError("Only the dataset owner or a superuser can do this")
