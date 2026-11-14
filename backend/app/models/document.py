import enum
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SQLAlchemyEnum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, JSONType, TimestampMixin, UUIDMixin, utc_now


class DocumentStatus(str, enum.Enum):
    UPLOADING = "UPLOADING"
    QUEUED = "QUEUED"
    VALIDATING = "VALIDATING"
    TEXT_EXTRACTION = "TEXT_EXTRACTION"
    CHUNKING = "CHUNKING"
    EMBEDDING = "EMBEDDING"
    VECTOR_INDEXING = "VECTOR_INDEXING"
    KNOWLEDGE_GRAPH = "KNOWLEDGE_GRAPH"
    READY = "READY"
    FAILED = "FAILED"
    ARCHIVED = "ARCHIVED"

    @property
    def is_terminal(self) -> bool:
        return self in (DocumentStatus.READY, DocumentStatus.FAILED, DocumentStatus.ARCHIVED)


class EmbeddingStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class GraphStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class Document(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "documents"

    # Identity & location
    filename: Mapped[str] = mapped_column(String(512), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(512), index=True, nullable=False)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)

    # Ownership
    workspace_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), index=True, nullable=False
    )
    owner_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )

    # File properties
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    page_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Pipeline status
    status: Mapped[DocumentStatus] = mapped_column(
        SQLAlchemyEnum(DocumentStatus, native_enum=False, length=32),
        default=DocumentStatus.UPLOADING,
        index=True,
        nullable=False,
    )
    embedding_status: Mapped[EmbeddingStatus] = mapped_column(
        SQLAlchemyEnum(EmbeddingStatus, native_enum=False, length=32),
        default=EmbeddingStatus.PENDING,
        nullable=False,
    )
    graph_status: Mapped[GraphStatus] = mapped_column(
        SQLAlchemyEnum(GraphStatus, native_enum=False, length=32),
        default=GraphStatus.PENDING,
        nullable=False,
    )

    current_stage: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    progress_percentage: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failure_reason: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    failure_stage: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    retryable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Timing
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, index=True, nullable=False
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    processing_duration: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Derived content
    summary: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    entity_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    relationship_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    metadata_json: Mapped[Dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)
    extracted_knowledge: Mapped[Dict[str, Any]] = mapped_column(
        JSONType, default=dict, nullable=False
    )

    versions: Mapped[List["DocumentVersion"]] = relationship(
        "DocumentVersion", back_populates="document", cascade="all, delete-orphan"
    )

    __table_args__ = (
        # Content-level dedupe is per workspace, not global: two tenants may
        # legitimately upload the same standards document.
        UniqueConstraint("workspace_id", "checksum", name="uq_documents_workspace_checksum"),
        Index("ix_documents_workspace_uploaded", "workspace_id", "uploaded_at"),
        Index("ix_documents_workspace_status", "workspace_id", "status"),
    )


class DocumentVersion(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "document_versions"

    document_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("documents.id", ondelete="CASCADE"), index=True, nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    storage_path: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    uploaded_by: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    document: Mapped["Document"] = relationship("Document", back_populates="versions")

    __table_args__ = (
        UniqueConstraint("document_id", "version", name="uq_document_versions_doc_version"),
    )
