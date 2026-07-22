import uuid
from sqlalchemy import Column, String, DateTime, Enum, JSON, Boolean, Float
from datetime import datetime, timezone
import enum
from app.db.session import Base

class DocumentStatus(str, enum.Enum):
    UPLOADED = "Uploaded"
    QUEUED = "Queued"
    PARSING = "Parsing"
    CHUNKING = "Chunking"
    ENTITY_EXTRACTION = "Entity Extraction"
    GRAPH_CONSTRUCTION = "Graph Construction"
    EMBEDDING = "Embedding"
    GRAPH_GENERATION = "Graph Generation"
    READY = "Ready"
    FAILED = "Failed"

class Document(Base):
    __tablename__ = "documents"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    filename = Column(String, index=True, nullable=False)
    file_path = Column(String, nullable=False)
    status = Column(Enum(DocumentStatus), default=DocumentStatus.UPLOADED)
    uploaded_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    processed_at = Column(DateTime, nullable=True)
    processing_duration = Column(Float, nullable=True)
    
    # Advanced Metadata
    metadata_json = Column(JSON, default=dict)
    
    # Structured Knowledge Extraction (Phase 5)
    extracted_knowledge = Column(JSON, default=dict)
    
    # Error Handling
    failure_stage = Column(String, nullable=True)
    error_message = Column(String, nullable=True)
    retryable = Column(Boolean, default=False)

