import requests
import time

url = "http://localhost:8000/api/v1/documents/upload/"
file_path = "real_dummy.pdf"
from reportlab.pdfgen import canvas

c = canvas.Canvas(file_path)
c.drawString(100, 750, "The Centrifugal Pump P-300 uses an outboard bearing.")
c.save()

with open(file_path, "rb") as f:
    files = {"file": f}
    response = requests.post(url, files=files)
    
print("Upload response:", response.status_code, response.json())
doc_id = response.json().get("id")

# Wait for processing
print("Waiting for processing...")
time.sleep(15)

res = requests.get(f"http://localhost:8000/api/v1/documents/")
for doc in res.json():
    if doc["id"] == doc_id:
        print(f"Status: {doc['status']}, Error: {doc.get('error_message')}")

res = requests.get("http://localhost:8000/api/v1/graph/stats")
print("Graph stats:", res.json())
