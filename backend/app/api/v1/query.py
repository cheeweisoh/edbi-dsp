import uuid

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.query import (DataQueryResponse, GenSQLRequest,
                               GenSQLResponse, SQLQueryRequest,
                               SQLQueryResponse)
from app.services.gensql_service import GenSQLService
from app.services.query_service import QueryService
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/datasets", tags=["query"])


def _svc(db: AsyncSession = Depends(get_db)) -> QueryService:
    return QueryService(db)


def _gensql_svc(db: AsyncSession = Depends(get_db)) -> GenSQLService:
    return GenSQLService(db)


@router.get("/{dataset_id}/data", response_model=DataQueryResponse)
async def read_dataset(dataset_id: uuid.UUID, limit: int | None = None, offset: int = 0, current_user: User = Depends(get_current_user), svc: QueryService = Depends(_svc)) -> DataQueryResponse:
    return await svc.read_dataset(dataset_id, current_user, limit=limit, offset=offset)


@router.post("/gensql", response_model=GenSQLResponse)
async def query_nl(data: GenSQLRequest, current_user: User = Depends(get_current_user), svc: GenSQLService = Depends(_gensql_svc)) -> GenSQLResponse:
    sql = await svc.generate_sql(
        data.nl_query,
        current_user,
        max_new_tokens=data.max_new_tokens,
    )
    return GenSQLResponse(sql=sql)


@router.post("/query", response_model=SQLQueryResponse)
async def query_sql(data: SQLQueryRequest, current_user: User = Depends(get_current_user), svc: QueryService = Depends(_svc)) -> SQLQueryResponse:
    return await svc.execute_sql(
        sql=data.sql,
        current_user=current_user,
        limit=data.limit,
        offset=data.offset,
    )
