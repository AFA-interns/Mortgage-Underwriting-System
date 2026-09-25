import sys
import json
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def run_test():
    payload = {
        "address": "100 Feet Road",
        "locality": "Indiranagar",
        "city": "Bangalore",
        "property_type": "Apartment",
        "bhk": 2,
        "area_sqft": 1200,
        "area_type": "carpet_area",
        "age_years": 5
    }

    print("--- Step 1: Submitting Application for Valuation ---")
    response = client.post("/api/v1/valuation/evaluate", json=payload)
    data = response.json()
    print(json.dumps(data, indent=2))

    if data.get("status") == "PENDING_HUMAN_REVIEW":
        thread_id = data.get("thread_id")
        print(f"\n--- Step 2: Human Review Triggered. Approving thread {thread_id}... ---")
        
        resume_payload = {"approved": True, "notes": "Approved by E2E test."}
        resume_resp = client.post(f"/api/v1/valuation/{thread_id}/resume", json=resume_payload)
        print("\n--- Step 3: Final Valuation Report ---")
        print(json.dumps(resume_resp.json(), indent=2))
    elif response.status_code == 200:
        print("\n--- Step 2: Final Valuation Report (No Human Review Required) ---")
    else:
        print(f"FAILED with status {response.status_code}")

if __name__ == "__main__":
    run_test()
