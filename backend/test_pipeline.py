import asyncio
import os
import PyPDF2
from reportlab.pdfgen import canvas
from app.db.session import SessionLocal
from app.models.document import Document
from app.tasks.document_tasks import process_document_task
from app.services.graph_service import graph_service

# Create a real PDF
pdf_path = "real_dummy.pdf"
c = canvas.Canvas(pdf_path)
c.drawString(100, 750, "The Centrifugal Pump P-200 uses an inboard bearing.")
c.save()

db = SessionLocal()
new_doc = Document(filename="real_dummy.pdf", file_path=pdf_path)
db.add(new_doc)
db.commit()
db.refresh(new_doc)

doc_id = new_doc.id

async def run():
    print("Starting process_document_task...")
    await process_document_task(doc_id)
    db.refresh(new_doc)
    print(f"Final status: {new_doc.status}")
    print(f"Error message: {new_doc.error_message}")
    
    ek = new_doc.extracted_knowledge
    if ek:
        entities = ek.get("entities", [])
        rels = ek.get("relationships", [])
        print(f"Extracted entities: {len(entities)}")
        print(f"Extracted relationships: {len(rels)}")
    else:
        print("No extracted knowledge.")
        
    print("Graph stats:", graph_service.get_stats())

asyncio.run(run())
