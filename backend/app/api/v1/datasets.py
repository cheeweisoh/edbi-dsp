import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.dataset import (
    DatasetCreate,
    DatasetMetadataResponse,
    DatasetMetadataUpsert,
    DatasetResponse,
    DatasetUpdate,
)
from app.services.dataset_service import DatasetService

router = APIRouter(prefix="/datasets", tags=["datasets"])


def _svc(db: AsyncSession = Depends(get_db)) -> DatasetService:
    return DatasetService(db)


@router.post("/", response_model=DatasetResponse, status_code=status.HTTP_201_CREATED)
async def create_dataset(
    data: DatasetCreate,
    current_user: User = Depends(get_current_user),
    svc: DatasetService = Depends(_svc),
) -> DatasetResponse:
    return await svc.create_dataset(data, current_user)


@router.get("/", response_model=list[DatasetResponse])
async def list_datasets(
    current_user: User = Depends(get_current_user),
    svc: DatasetService = Depends(_svc),
) -> list[DatasetResponse]:
    return await svc.list_datasets(current_user)


@router.get("/{dataset_id}", response_model=DatasetResponse)
async def get_dataset(
    dataset_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    svc: DatasetService = Depends(_svc),
) -> DatasetResponse:
    return await svc.get_dataset(dataset_id, current_user)


@router.put("/{dataset_id}", response_model=DatasetResponse)
async def update_dataset(
    dataset_id: uuid.UUID,
    data: DatasetUpdate,
    current_user: User = Depends(get_current_user),
    svc: DatasetService = Depends(_svc),
) -> DatasetResponse:
    return await svc.update_dataset(dataset_id, data, current_user)


@router.delete("/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dataset(
    dataset_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    svc: DatasetService = Depends(_svc),
) -> None:
    await svc.delete_dataset(dataset_id, current_user)


@router.get("/{dataset_id}/metadata", response_model=DatasetMetadataResponse)
async def get_metadata(
    dataset_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    svc: DatasetService = Depends(_svc),
) -> DatasetMetadataResponse:
    return await svc.get_metadata(dataset_id, current_user)


@router.put("/{dataset_id}/metadata", response_model=DatasetMetadataResponse)
async def upsert_metadata(
    dataset_id: uuid.UUID,
    data: DatasetMetadataUpsert,
    current_user: User = Depends(get_current_user),
    svc: DatasetService = Depends(_svc),
) -> DatasetMetadataResponse:
    return await svc.upsert_metadata(dataset_id, data, current_user)
