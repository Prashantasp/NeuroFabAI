import os
import shutil
from typing import List
from fastapi import APIRouter, Depends, UploadFile, File, BackgroundTasks, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.schemas.document import DocumentResponse
from app.tasks.document_tasks import process_document_task
from app.services.document_service import document_service
from app.core.config import get_settings

router = APIRouter()
settings = get_settings()

UPLOAD_DIR = os.path.join(os.getcwd(), "data", "documents")
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/upload/", response_model=DocumentResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported for now.")
        
    file_location = os.path.join(UPLOAD_DIR, file.filename)
    
    # Save file to disk
    with open(file_location, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    # Delegate to service layer for db interactions
    db_document = document_service.create_document(db, file.filename, file_location)
    
    # Queue background task for processing
    background_tasks.add_task(process_document_task, db_document.id)
    
    return db_document

@router.get("/", response_model=List[DocumentResponse])
def list_documents(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    documents = document_service.get_documents(db, skip=skip, limit=limit)
    return documents
