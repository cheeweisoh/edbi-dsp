import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, JSON, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class DatasetMetadata(Base):
    __tablename__ = "dataset_metadata"

    dataset_id: Mapped[uuid.UUID] = mapped_column(Uuid(native_uuid=False), ForeignKey("datasets.id", ondelete="CASCADE"), primary_key=True)
    schema_name: Mapped[str | None] = mapped_column(String, nullable=True)
    table_name: Mapped[str | None] = mapped_column(String, nullable=True)
    source_system: Mapped[str | None] = mapped_column(String, nullable=True)
    file_path: Mapped[str | None] = mapped_column(String, nullable=True)
    row_count: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    size_in_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    last_refreshed: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)

    dataset: Mapped["Dataset"] = relationship("Dataset", back_populates="dataset_metadata")  # noqa: F821
