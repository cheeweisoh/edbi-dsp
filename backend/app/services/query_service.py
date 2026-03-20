import time
import uuid
from pathlib import Path

import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.exceptions import NotFoundError
from app.models.user import User
from app.repositories.dataset_repo import DatasetRepository
from app.repositories.query_log_repo import QueryLogRepository
from app.schemas.query import DataQueryResponse
from app.services.permission_service import PermissionService


class QueryService:
    def __init__(self, db: AsyncSession) -> None:
        self.dataset_repo = DatasetRepository(db)
        self.log_repo = QueryLogRepository(db)
        self.perm_svc = PermissionService(db)

    async def read_dataset(
        self,
        dataset_id: uuid.UUID,
        current_user: User,
        limit: int | None = None,
        offset: int = 0,
    ) -> DataQueryResponse:
        await self.perm_svc.verify_access(current_user, dataset_id, min_permission="query")

        dm = await self.dataset_repo.get_metadata(dataset_id)
        if dm is None or not dm.file_path:
            raise NotFoundError(f"No file path configured for dataset {dataset_id}")

        file_path = Path(settings.FILE_BASE_DIR) / dm.file_path
        if not file_path.exists():
            raise NotFoundError(f"Data file not found: {dm.file_path}")

        t0 = time.monotonic()
        df = pd.read_csv(file_path)
        total_row_count = len(df)

        sliced = df.iloc[offset : (offset + limit) if limit is not None else None]
        normalized = sliced.astype(object).where(pd.notna(sliced), other=None)
        rows = normalized.to_dict(orient="records")
        elapsed_ms = int((time.monotonic() - t0) * 1000)

        await self.log_repo.create(
            user_id=current_user.id,
            dataset_id=dataset_id,
            executed_sql=f"READ CSV {dm.file_path}",
            execution_time_ms=elapsed_ms,
            row_count=len(rows),
        )

        return DataQueryResponse(
            dataset_id=dataset_id,
            file_path=dm.file_path,
            columns=list(df.columns),
            rows=rows,
            row_count=len(rows),
            total_row_count=total_row_count,
        )
