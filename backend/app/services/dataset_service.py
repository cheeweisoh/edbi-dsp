import uuid

from app.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.models.dataset import Dataset
from app.models.dataset_metadata import DatasetMetadata
from app.models.user import User
from app.repositories.dataset_repo import DatasetRepository
from app.schemas.dataset import (DatasetCreate, DatasetMetadataUpsert,
                                 DatasetUpdate)
from app.services.permission_service import PermissionService
from sqlalchemy.ext.asyncio import AsyncSession


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
            datasets = await self.repo.list_active()
        else:
            accessible_ids = await self.perm_svc.get_accessible_dataset_ids(current_user)
            datasets = await self.repo.list_accessible(current_user.id, accessible_ids)

        groups: list[tuple[set[str], Dataset]] = []
        for dataset in datasets:
            table_keys = await self._canonical_table_keys(dataset)
            matched_group_index: int | None = None
            for idx, (group_keys, _) in enumerate(groups):
                if group_keys.intersection(table_keys):
                    matched_group_index = idx
                    break

            if matched_group_index is None:
                groups.append((set(table_keys), dataset))
                continue

            group_keys, chosen = groups[matched_group_index]
            group_keys.update(table_keys)
            if self._display_name_rank(self._dataset_label(dataset)) > self._display_name_rank(self._dataset_label(chosen)):
                groups[matched_group_index] = (group_keys, dataset)

        return [dataset for _, dataset in groups]

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

    async def _canonical_table_keys(self, dataset: Dataset) -> set[str]:
        refs: set[str] = set()
        dm = await self.repo.get_metadata(dataset.id)
        if dm is not None and isinstance(dm.metadata_json, dict):
            unity_catalog = dm.metadata_json.get("unity_catalog")
            if isinstance(unity_catalog, dict):
                full_name = unity_catalog.get("full_name")
                if isinstance(full_name, str) and full_name.strip():
                    refs.add(full_name)
                uc_table = unity_catalog.get("table_name")
                if isinstance(uc_table, str) and uc_table.strip():
                    refs.add(uc_table)
            metadata_id = dm.metadata_json.get("id")
            if isinstance(metadata_id, str) and metadata_id.strip():
                refs.add(metadata_id)
        if dm is not None and dm.file_path:
            refs.add(dm.file_path)
        if dm is not None and dm.schema_name and dm.table_name:
            refs.add(f"{dm.schema_name}.{dm.table_name}")
        if dm is not None and dm.table_name:
            refs.add(dm.table_name)
        dataset_name = getattr(dataset, "dataset_name", None)
        if isinstance(dataset_name, str) and dataset_name.strip():
            refs.add(dataset_name)
        name = getattr(dataset, "name", None)
        if isinstance(name, str) and name.strip():
            refs.add(name)
        display_name = getattr(dataset, "display_name", None)
        if isinstance(display_name, str) and display_name.strip():
            refs.add(display_name)
        # Always include the user-facing label so snake_case/title-case pairs collapse.
        refs.add(self._dataset_label(dataset))

        canonical: set[str] = set()
        for ref in refs:
            canonical.update(self._normalize_table_ref(ref))
        if canonical:
            return canonical
        # If there is no metadata, preserve current behavior and keep the dataset distinct.
        return {f"dataset:{dataset.id}"}

    @staticmethod
    def _display_name_rank(name: str) -> tuple[int, int]:
        score = 0
        if "." not in name:
            score += 1
        if "_" not in name:
            score += 1
        if " " in name:
            score += 1
        if name == name.title():
            score += 1
        # Prefer shorter, cleaner labels when scores tie.
        return (score, -len(name))

    @staticmethod
    def _dataset_label(dataset: Dataset) -> str:
        display_name = getattr(dataset, "display_name", None)
        if isinstance(display_name, str) and display_name.strip():
            return display_name
        name = getattr(dataset, "name", None)
        if isinstance(name, str) and name.strip():
            return name
        dataset_name = getattr(dataset, "dataset_name", None)
        if isinstance(dataset_name, str) and dataset_name.strip():
            return dataset_name
        return str(dataset.id)

    @staticmethod
    def _normalize_table_ref(ref: str) -> set[str]:
        cleaned = ref.replace("`", "").replace('"', "").strip().lower().replace(" ", "_")
        if not cleaned:
            return set()
        parts = [part for part in cleaned.split(".") if part]
        if not parts:
            return {cleaned}
        variants = {".".join(parts), parts[-1]}
        if len(parts) >= 2:
            variants.add(".".join(parts[-2:]))
        return variants
