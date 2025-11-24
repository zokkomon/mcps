import requests
import uvicorn
import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from dotenv import load_dotenv

load_dotenv()

HUBSPOT_API_KEY = os.getenv("HUBSPOT_API_KEY")
HUBSPOT_API_URL = "https://api.hubapi.com"

if not HUBSPOT_API_KEY:
    raise ValueError("ERROR: HUBSPOT_API_KEY not found!")

headers = {
    "Authorization": f"Bearer {HUBSPOT_API_KEY}",
    "Content-Type": "application/json"
}

app = FastAPI(title="HubSpot MCP Server - Lead Status Fix")

class ContactQuery(BaseModel):
    email: str

class ActivityQuery(BaseModel):
    contact_email: str
    limit: Optional[int] = 20

class ListQuery(BaseModel):
    limit: Optional[int] = 20

# --- HELPER ---
def fetch_batch_details(contact_id, obj_type, properties):
    # 1. Get IDs
    assoc_url = f"{HUBSPOT_API_URL}/crm/v4/objects/contacts/{contact_id}/associations/{obj_type}"
    r = requests.get(assoc_url, headers=headers)
    if not r.ok: return []
    ids = [{"id": x["toObjectId"]} for x in r.json().get("results", [])]
    if not ids: return []

    # 2. Get Details
    batch_url = f"{HUBSPOT_API_URL}/crm/v3/objects/{obj_type}/batch/read"
    r_batch = requests.post(batch_url, headers=headers, json={"inputs": ids, "properties": properties})
    return r_batch.json().get("results", []) if r_batch.ok else []

# --- ENDPOINTS ---

@app.post("/tool/list_contacts")
def list_contacts(req: ListQuery):
    try:
        url = f"{HUBSPOT_API_URL}/crm/v3/objects/contacts"
        # Fetch lead status right here in the list for efficiency
        params = {
            "limit": req.limit, 
            "properties": ["email", "firstname", "lastname", "hs_lead_status"], 
            "sort": "-updatedate"
        }
        r = requests.get(url, headers=headers, params=params)
        contacts = []
        for res in r.json().get("results", []):
            p = res.get("properties", {})
            if p.get("email"):
                contacts.append({
                    "email": p.get("email"),
                    "name": f"{p.get('firstname', '')} {p.get('lastname', '')}".strip(),
                    "status": p.get("hs_lead_status") # Pass it through
                })
        return {"count": len(contacts), "contacts": contacts}
    except Exception as e:
        return {"error": str(e)}

@app.post("/tool/get_contact_status")
def get_contact_status(req: ContactQuery):
    try:
        url = f"{HUBSPOT_API_URL}/crm/v3/objects/contacts/search"
        payload = {
            "limit": 1,
            "properties": ["firstname", "lastname", "email", "lifecyclestage", "hs_lead_status", "company"],
            "filterGroups": [{"filters": [{"propertyName": "email", "operator": "EQ", "value": req.email}]}]
        }
        r = requests.post(url, headers=headers, json=payload)
        results = r.json().get("results", [])
        if not results: return {"contact_found": False}
        
        p = results[0].get("properties", {})
        
        # --- CRITICAL FIX: Return 'hs_lead_status' ---
        return {
            "contact_found": True,
            "lifecyclestage": p.get("lifecyclestage"),
            "hs_lead_status": p.get("hs_lead_status"), 
            "company": p.get("company")
        }
    except Exception as e:
        return {"error": str(e)}

@app.post("/tool/get_activities")
def get_activities(req: ActivityQuery):
    try:
        # Find ID
        url = f"{HUBSPOT_API_URL}/crm/v3/objects/contacts/search"
        r = requests.post(url, headers=headers, json={
            "filterGroups": [{"filters": [{"propertyName": "email", "operator": "EQ", "value": req.contact_email}]}]
        })
        results = r.json().get("results", [])
        if not results: return {"contact_found": False}
        cid = results[0].get("id")
        
        activities = []

        # Tasks
        for t in fetch_batch_details(cid, "tasks", ["hs_task_subject", "hs_task_status", "hs_timestamp"]):
            activities.append({
                "type": "TASK",
                "date": t["properties"].get("hs_timestamp"),
                "status": t["properties"].get("hs_task_status", "OPEN"),
                "summary": t["properties"].get("hs_task_subject")
            })

        # Calls
        for c in fetch_batch_details(cid, "calls", ["hs_call_title", "hs_call_status", "hs_timestamp"]):
            activities.append({
                "type": "CALL",
                "date": c["properties"].get("hs_timestamp"),
                "status": c["properties"].get("hs_call_status", "LOGGED"),
                "summary": c["properties"].get("hs_call_title")
            })

        # Meetings
        for m in fetch_batch_details(cid, "meetings", ["hs_meeting_title", "hs_meeting_outcome", "hs_meeting_start_time"]):
            activities.append({
                "type": "MEETING",
                "date": m["properties"].get("hs_meeting_start_time"),
                "status": m["properties"].get("hs_meeting_outcome", "SCHEDULED"),
                "summary": m["properties"].get("hs_meeting_title")
            })

        activities.sort(key=lambda x: x.get("date") or "0", reverse=True)
        return {"activities": activities}

    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)