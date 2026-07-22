from sqlalchemy.orm import Session
from app.models.document import Document, DocumentStatus
from typing import List, Optional

class DocumentService:
    def create_document(self, db: Session, filename: str, file_path: str) -> Document:
        db_document = Document(
            filename=filename,
            file_path=file_path,
            status=DocumentStatus.QUEUED
        )
        db.add(db_document)
        db.commit()
        db.refresh(db_document)
        return db_document

    def get_document(self, db: Session, document_id: str) -> Optional[Document]:
        return db.query(Document).filter(Document.id == document_id).first()

    def get_documents(self, db: Session, skip: int = 0, limit: int = 100) -> List[Document]:
        return db.query(Document).offset(skip).limit(limit).all()

document_service = DocumentService()
