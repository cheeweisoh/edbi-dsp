import uuid

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.repositories.user_repo import UserRepository
from app.schemas.dataset import (DatasetCreate, DatasetMetadataResponse,
                                 DatasetMetadataUpsert, DatasetListResponse,
                                 DatasetResponse,
                                 DatasetUpdate)
from app.services.dataset_service import DatasetService
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

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


@router.get("/", response_model=list[DatasetListResponse])
async def list_datasets(
    current_user: User = Depends(get_current_user),
    svc: DatasetService = Depends(_svc),
    db: AsyncSession = Depends(get_db),
) -> list[DatasetListResponse]:
    datasets = await svc.list_datasets(current_user)
    user_repo = UserRepository(db)
    owner_ids = {dataset.owner_id for dataset in datasets}
    owners = {owner_id: await user_repo.get_by_id(owner_id) for owner_id in owner_ids}
    return [
        DatasetListResponse(
            id=dataset.id,
            table_name=getattr(dataset, "dataset_name", dataset.name),
            display_name=getattr(dataset, "display_name", dataset.name),
            name=getattr(dataset, "display_name", dataset.name),
            description=dataset.description,
            owner_id=dataset.owner_id,
            owner_name=owners.get(dataset.owner_id).full_name if owners.get(dataset.owner_id) else None,
            owner_email=owners.get(dataset.owner_id).email if owners.get(dataset.owner_id) else None,
            is_active=dataset.is_active,
            created_at=dataset.created_at,
            updated_at=dataset.updated_at,
        )
        for dataset in datasets
    ]


@router.get("/{dataset_id}", response_model=DatasetResponse)
async def get_dataset(
    dataset_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    svc: DatasetService = Depends(_svc),
    db: AsyncSession = Depends(get_db),
) -> DatasetResponse:
    dataset = await svc.get_dataset(dataset_id, current_user)
    owner = await UserRepository(db).get_by_id(dataset.owner_id)
    return DatasetResponse(
        id=dataset.id,
        name=dataset.name,
        description=dataset.description,
        owner_id=dataset.owner_id,
        owner_name=owner.full_name if owner else None,
        owner_email=owner.email if owner else None,
        is_active=dataset.is_active,
        created_at=dataset.created_at,
        updated_at=dataset.updated_at,
    )


@router.put("/{dataset_id}", response_model=DatasetResponse)
async def update_dataset(
    dataset_id: uuid.UUID,
    data: DatasetUpdate,
    current_user: User = Depends(get_current_user),
    svc: DatasetService = Depends(_svc),
    db: AsyncSession = Depends(get_db),
) -> DatasetResponse:
    dataset = await svc.update_dataset(dataset_id, data, current_user)
    owner = await UserRepository(db).get_by_id(dataset.owner_id)
    return DatasetResponse(
        id=dataset.id,
        name=dataset.name,
        description=dataset.description,
        owner_id=dataset.owner_id,
        owner_name=owner.full_name if owner else None,
        owner_email=owner.email if owner else None,
        is_active=dataset.is_active,
        created_at=dataset.created_at,
        updated_at=dataset.updated_at,
    )


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
    db: AsyncSession = Depends(get_db),
) -> DatasetMetadataResponse:
    metadata = await svc.get_metadata(dataset_id, current_user)
    dataset = await svc.get_dataset(dataset_id, current_user)
    owner = await UserRepository(db).get_by_id(dataset.owner_id)
    return DatasetMetadataResponse(
        dataset_id=metadata.dataset_id,
        schema_name=metadata.schema_name,
        table_name=metadata.table_name,
        source_system=metadata.source_system,
        file_path=metadata.file_path,
        row_count=metadata.row_count,
        size_in_bytes=metadata.size_in_bytes,
        last_refreshed=metadata.last_refreshed,
        metadata_json=metadata.metadata_json,
        owner_id=dataset.owner_id,
        owner_name=owner.full_name if owner else None,
        owner_email=owner.email if owner else None,
    )


@router.put("/{dataset_id}/metadata", response_model=DatasetMetadataResponse)
async def upsert_metadata(
    dataset_id: uuid.UUID,
    data: DatasetMetadataUpsert,
    current_user: User = Depends(get_current_user),
    svc: DatasetService = Depends(_svc),
    db: AsyncSession = Depends(get_db),
) -> DatasetMetadataResponse:
    metadata = await svc.upsert_metadata(dataset_id, data, current_user)
    dataset = await svc.get_dataset(dataset_id, current_user)
    owner = await UserRepository(db).get_by_id(dataset.owner_id)
    return DatasetMetadataResponse(
        dataset_id=metadata.dataset_id,
        schema_name=metadata.schema_name,
        table_name=metadata.table_name,
        source_system=metadata.source_system,
        file_path=metadata.file_path,
        row_count=metadata.row_count,
        size_in_bytes=metadata.size_in_bytes,
        last_refreshed=metadata.last_refreshed,
        metadata_json=metadata.metadata_json,
        owner_id=dataset.owner_id,
        owner_name=owner.full_name if owner else None,
        owner_email=owner.email if owner else None,
    )
