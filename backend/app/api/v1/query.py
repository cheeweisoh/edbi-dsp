import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.query import DataQueryResponse, QueryNLRequest, QueryNLResponse
from app.services.querynl_service import QueryNLService
from app.services.query_service import QueryService

router = APIRouter(prefix="/datasets", tags=["query"])


def _svc(db: AsyncSession = Depends(get_db)) -> QueryService:
    return QueryService(db)


def _querynl_svc(db: AsyncSession = Depends(get_db)) -> QueryNLService:
    return QueryNLService(db)


@router.get("/{dataset_id}/data", response_model=DataQueryResponse)
async def read_dataset(
    dataset_id: uuid.UUID,
    limit: int | None = None,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    svc: QueryService = Depends(_svc),
) -> DataQueryResponse:
    return await svc.read_dataset(dataset_id, current_user, limit=limit, offset=offset)


@router.post("/{dataset_id}/querynl", response_model=QueryNLResponse)
async def query_nl(
    dataset_id: uuid.UUID,
    data: QueryNLRequest,
    current_user: User = Depends(get_current_user),
    svc: QueryNLService = Depends(_querynl_svc),
) -> QueryNLResponse:
    sql = await svc.generate_sql(
        dataset_id,
        data.nl_query,
        current_user,
        max_new_tokens=data.max_new_tokens,
    )
    return QueryNLResponse(sql=sql)
