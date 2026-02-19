from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# Import all models here so that Base.metadata is populated for Alembic and init_db
from app.models import user, dataset, dataset_metadata, query_log, group, group_member, dataset_permission  # noqa: E402, F401
