import requests
import time
import json
import os

BASE_URL = "http://localhost:8000/api/v1"

def upload_document():
    print("Uploading test document...")
    files = {'file': open('test_sop.pdf', 'rb')}
    requests.post(f"{BASE_URL}/documents/upload/", files=files)
    print("Waiting 12 seconds for the background ingestion pipeline to complete...")
    time.sleep(12)

def ask_question(query: str):
    print(f"\n{'='*80}")
    print(f"QUESTION: {query}")
    print(f"{'='*80}")
    
    response = requests.post(f"{BASE_URL}/chat/ask", json={"query": query})
    if response.status_code != 200:
        print(f"Error: {response.status_code} - {response.text}")
        return
        
    data = response.json()
    
    print("\n[ REASONING TIMELINE ]")
    for event in data.get("reasoning_timeline", []):
        print(f"  -> [{event['agent_name']}] {event['action']} ({event['duration_ms']:.2f}ms)")
        print(f"       {event['summary']}")
    
    errors = data.get("errors", [])
    if errors:
        print(f"\n[ ERRORS RECOVERED FROM ]")
        for e in errors:
            print(f"  - {e}")
            
    decision = data.get("decision", {})
    if decision:
        print(f"\n[ DECISION RESPONSE ]")
        print(f"Summary:       {decision.get('executive_summary')}")
        print(f"Root Cause:    {decision.get('root_cause')}")
        print(f"Rec. Action:   {decision.get('recommended_action')}")
        print(f"Impact:        {decision.get('business_impact')}")
        print(f"Risk:          {decision.get('risk_level')}")
        print(f"Confidence:    {decision.get('confidence')}")
        print(f"Evidence:      {len(decision.get('supporting_evidence', []))} items")
    print(f"{'='*80}\n")

if __name__ == "__main__":
    if not os.path.exists('test_sop.pdf'):
        with open('test_sop.pdf', 'wb') as f:
            f.write(b"%PDF-1.4\n%Fake PDF for testing\n")
            
    upload_document()
    
    # 1. Full Pipeline (Coordinator -> Search -> Graph -> Maintenance -> Coordinator)
    ask_question("Why is Pump P-101 overheating?")
    
    # 2. Semantic Pipeline (Coordinator -> Search -> Coordinator)
    ask_question("Find the SOP.")
    
    # 3. Failure Handling Pipeline (Coordinator -> Search -> Graph -> Maintenance(CRASH) -> Coordinator)
    ask_question("Why did it fail?")
