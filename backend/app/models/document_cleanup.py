"""Deletion outbox, committed in the same transaction as removal of a document."""

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, JSONType, TimestampMixin


class DocumentCleanup(Base, TimestampMixin):
    __tablename__ = "document_cleanup"

    document_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(36), index=True)
    file_paths: Mapped[list] = mapped_column(JSONType, default=list)
