import uuid

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dataset import Dataset
from app.models.dataset_metadata import DatasetMetadata


class DatasetRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, **kwargs: object) -> Dataset:
        dataset = Dataset(**kwargs)
        self.db.add(dataset)
        await self.db.commit()
        await self.db.refresh(dataset)
        return dataset

    async def get_by_id(self, dataset_id: uuid.UUID) -> Dataset | None:
        result = await self.db.execute(select(Dataset).where(Dataset.id == dataset_id))
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str) -> Dataset | None:
        result = await self.db.execute(
            select(Dataset).where(
                (Dataset.display_name == name) | (Dataset.dataset_name == name)
            )
        )
        return result.scalar_one_or_none()

    async def list_active(self) -> list[Dataset]:
        result = await self.db.execute(select(Dataset).where(Dataset.is_active.is_(True)))
        return list(result.scalars().all())

    async def list_accessible(self, owner_id: uuid.UUID, accessible_ids: set[uuid.UUID]) -> list[Dataset]:
        result = await self.db.execute(
            select(Dataset).where(
                Dataset.is_active.is_(True),
                or_(Dataset.owner_id == owner_id, Dataset.id.in_(accessible_ids)),
            )
        )
        return list(result.scalars().all())

    async def update(self, dataset: Dataset, **kwargs: object) -> Dataset:
        for key, value in kwargs.items():
            setattr(dataset, key, value)
        await self.db.commit()
        await self.db.refresh(dataset)
        return dataset

    async def get_metadata(self, dataset_id: uuid.UUID) -> DatasetMetadata | None:
        result = await self.db.execute(select(DatasetMetadata).where(DatasetMetadata.dataset_id == dataset_id))
        return result.scalar_one_or_none()

    async def upsert_metadata(self, dataset_id: uuid.UUID, **kwargs: object) -> DatasetMetadata:
        dm = await self.get_metadata(dataset_id)
        if dm is None:
            dm = DatasetMetadata(dataset_id=dataset_id, **kwargs)
            self.db.add(dm)
        else:
            for key, value in kwargs.items():
                setattr(dm, key, value)
        await self.db.commit()
        await self.db.refresh(dm)
        return dm
