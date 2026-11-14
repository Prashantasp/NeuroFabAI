from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.document import DocumentStatus, EmbeddingStatus, GraphStatus


class DocumentResponse(BaseModel):
    """Everything the Knowledge Hub renders for a document.

    The previous version omitted `current_stage`, `progress_percentage` and
    `failure_reason`, which the UI read unconditionally -- so the progress bar
    and failure message could never display.
    """

    id: str
    workspace_id: str
    owner_id: str

    title: str
    filename: str
    file_size: int
    mime_type: str
    checksum: str
    version: int
    page_count: Optional[int] = None

    status: DocumentStatus
    embedding_status: EmbeddingStatus
    graph_status: GraphStatus
    current_stage: Optional[str] = None
    progress_percentage: int = 0
    failure_reason: Optional[str] = None
    failure_stage: Optional[str] = None
    error_message: Optional[str] = None
    retryable: bool = False
    retry_count: int = 0

    uploaded_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    processed_at: Optional[datetime] = None
    processing_duration: Optional[float] = None

    summary: Optional[str] = None
    chunk_count: int = 0
    entity_count: int = 0
    relationship_count: int = 0

    metadata_json: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True)


class DocumentDetailResponse(DocumentResponse):
    """Adds the full extracted graph. Only fetched for a single document."""

    extracted_knowledge: Dict[str, Any] = Field(default_factory=dict)
