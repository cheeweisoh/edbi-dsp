import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

# Valid values for the permission column
PERMISSION_LEVELS: dict[str, int] = {"view": 1, "query": 2, "edit": 3, "admin": 4}


def permissions_at_least(min_perm: str) -> list[str]:
    """Return all permission strings that satisfy >= min_perm."""
    level = PERMISSION_LEVELS[min_perm]
    return [p for p, l in PERMISSION_LEVELS.items() if l >= level]


class DatasetPermission(Base):
    __tablename__ = "dataset_permissions"
    __table_args__ = (
        UniqueConstraint("dataset_id", "grantee_type", "grantee_id", name="uq_dataset_grantee"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(native_uuid=False), primary_key=True, default=uuid.uuid4)
    dataset_id: Mapped[uuid.UUID] = mapped_column(Uuid(native_uuid=False), ForeignKey("datasets.id", ondelete="CASCADE"))
    grantee_type: Mapped[str] = mapped_column(String)   # "user" | "group"
    grantee_id: Mapped[uuid.UUID] = mapped_column(Uuid(native_uuid=False))
    permission: Mapped[str] = mapped_column(String)     # "view" | "query" | "edit" | "admin"
    granted_by: Mapped[uuid.UUID] = mapped_column(Uuid(native_uuid=False), ForeignKey("users.id"))
    granted_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
