import requests
import time
import json
import os

BASE_URL = "http://localhost:8000/api/v1"

def upload_document():
    print("Uploading test document...")
    files = {'file': open('test_sop.pdf', 'rb')}
    response = requests.post(f"{BASE_URL}/documents/upload/", files=files)
    print(f"Upload Response: {response.json()}")
    
    print("Waiting 12 seconds for the background ingestion pipeline to complete...")
    time.sleep(12)

def ask_question(query: str):
    print(f"\n{'='*60}")
    print(f"QUESTION: {query}")
    print(f"{'='*60}")
    
    response = requests.post(f"{BASE_URL}/chat/ask", json={"query": query})
    if response.status_code != 200:
        print(f"Error: {response.status_code} - {response.text}")
        return
        
    data = response.json()
    
    plan = data.get("query_plan", {})
    print(f"--- QUERY PLANNER ---")
    print(f"Intent: {plan.get('detected_intent')}")
    print(f"Strategy: {plan.get('selected_strategy')}")
    print(f"Entities Extracted: {plan.get('extracted_entities')}")
    
    fusion = data.get("fused_evidence", {})
    print(f"\n--- RETRIEVAL & FUSION ---")
    print(f"Chunks Retrieved: {len(fusion.get('retrieved_chunks', []))}")
    print(f"Nodes Retrieved: {len(fusion.get('retrieved_nodes', []))}")
    print(f"Edges Retrieved: {len(fusion.get('retrieved_relationships', []))}")
    
    answer = data.get("explainable_answer", {})
    print(f"\n--- EXPLAINABLE ANSWER ---")
    print(f"Answer: {answer.get('answer')}")
    print(f"Reasoning: {answer.get('reasoning')}")
    print(f"Confidence: {answer.get('confidence')} ({answer.get('confidence_label')})")
    print(f"Action: {answer.get('recommended_action')}")
    print(f"Risk: {answer.get('risk_level')}")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    if not os.path.exists('test_sop.pdf'):
        # Create dummy PDF for testing if needed
        with open('test_sop.pdf', 'wb') as f:
            f.write(b"%PDF-1.4\n%Fake PDF for testing\n")
            
    upload_document()
    
    # 1. Troubleshooting (Hybrid)
    ask_question("Why is Pump P-101 overheating?")
    
    # 2. Semantic Lookup (Vector)
    ask_question("Which SOP discusses bearing maintenance?")
    
    # 3. Relationship Reasoning (Graph)
    ask_question("What components are related to Pump P-101?")
