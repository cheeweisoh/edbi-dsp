import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.query import DataQueryResponse
from app.services.query_service import QueryService

router = APIRouter(prefix="/datasets", tags=["query"])


def _svc(db: AsyncSession = Depends(get_db)) -> QueryService:
    return QueryService(db)


@router.get("/{dataset_id}/data", response_model=DataQueryResponse)
async def read_dataset(
    dataset_id: uuid.UUID,
    limit: int | None = None,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    svc: QueryService = Depends(_svc),
) -> DataQueryResponse:
    return await svc.read_dataset(dataset_id, current_user, limit=limit, offset=offset)
