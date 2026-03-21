from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# Import all models here so that Base.metadata is populated for Alembic and init_db
from app.models import (dataset, dataset_metadata,  # noqa: E402, F401
                        dataset_permission, group, group_member, query_log,
                        user)
