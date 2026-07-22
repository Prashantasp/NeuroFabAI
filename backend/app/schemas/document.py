from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional
from app.models.document import DocumentStatus

class DocumentBase(BaseModel):
    filename: str
    status: DocumentStatus

class DocumentCreate(DocumentBase):
    file_path: str

class DocumentResponse(DocumentBase):
    id: str
    uploaded_at: datetime
    processed_at: Optional[datetime] = None
    processing_duration: Optional[float] = None
    metadata_json: dict
    extracted_knowledge: Optional[dict] = None
    
    failure_stage: Optional[str] = None
    error_message: Optional[str] = None
    retryable: bool = False
    
    model_config = ConfigDict(from_attributes=True)
