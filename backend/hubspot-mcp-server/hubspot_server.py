import sys
import os
import httpx
from typing import Dict, Optional, List
from mcp.server.fastmcp import FastMCP

# Create an MCP server
mcp = FastMCP("HubSpot MCP")

# Environment variables
HUBSPOT_API_KEY = os.environ.get("HUBSPOT_API_KEY")
HUBSPOT_API_URL = "https://api.hubapi.com"

if not HUBSPOT_API_KEY:
    print("Warning: HUBSPOT_API_KEY environment variable not configured.", file=sys.stderr)

def get_headers():
    return {
        "Authorization": f"Bearer {HUBSPOT_API_KEY}",
        "Content-Type": "application/json"
    }

async def make_hubspot_request(method: str, endpoint: str, data: Dict = None, params: Dict = None) -> Dict:
    headers = get_headers()
    url = f"{HUBSPOT_API_URL}{endpoint}"
    
    async with httpx.AsyncClient() as client:
        response = await client.request(method, url, headers=headers, json=data, params=params)
        
        if response.status_code >= 400:
            print(f"HubSpot API Error {response.status_code}: {response.text}", file=sys.stderr)
            return {
                "error": True,
                "status_code": response.status_code,
                "message": response.text
            }
            
        return response.json()

async def fetch_batch_details(contact_id: str, obj_type: str, properties: List[str]) -> List[Dict]:
    """Helper function to fetch associated objects in batch"""
    # 1. Get association IDs
    assoc_result = await make_hubspot_request(
        "GET", 
        f"/crm/v4/objects/contacts/{contact_id}/associations/{obj_type}"
    )
    
    if "error" in assoc_result or not assoc_result.get("results"):
        return []
    
    ids = [{"id": x["toObjectId"]} for x in assoc_result.get("results", [])]
    
    # 2. Get details in batch
    batch_result = await make_hubspot_request(
        "POST",
        f"/crm/v3/objects/{obj_type}/batch/read",
        data={"inputs": ids, "properties": properties}
    )
    
    if "error" in batch_result:
        return []
    
    return batch_result.get("results", [])

# === TOOLS ===

@mcp.tool()
async def list_contacts(limit: int = 20) -> str:
    """List recent contacts from HubSpot."""
    params = {
        "limit": limit,
        "properties": ["email", "firstname", "lastname", "hs_lead_status"],
        "sort": "-updatedate"
    }
    
    result = await make_hubspot_request("GET", "/crm/v3/objects/contacts", params=params)
    
    if "error" in result:
        return f"Error listing contacts: {result.get('message', 'Unknown error')}"
    
    contacts = []
    for res in result.get("results", []):
        props = res.get("properties", {})
        email = props.get("email")
        if email:
            name = f"{props.get('firstname', '')} {props.get('lastname', '')}".strip()
            status = props.get("hs_lead_status", "UNKNOWN")
            contacts.append(f"{email} | {name} | Status: {status}")
    
    if not contacts:
        return "No contacts found."
    
    return f"Found {len(contacts)} contacts:\n" + "\n".join(contacts)

@mcp.tool()
async def get_contact_status(email: str) -> str:
    """Get the status and details of a contact by email."""
    payload = {
        "limit": 1,
        "properties": ["firstname", "lastname", "email", "lifecyclestage", "hs_lead_status", "company"],
        "filterGroups": [{
            "filters": [{
                "propertyName": "email",
                "operator": "EQ",
                "value": email
            }]
        }]
    }
    
    result = await make_hubspot_request("POST", "/crm/v3/objects/contacts/search", data=payload)
    
    if "error" in result:
        return f"Error searching contact: {result.get('message', 'Unknown error')}"
    
    results = result.get("results", [])
    if not results:
        return f"Contact not found: {email}"
    
    props = results[0].get("properties", {})
    
    formatted = [
        f"Contact: {props.get('firstname', '')} {props.get('lastname', '')}",
        f"Email: {props.get('email', 'N/A')}",
        f"Lead Status: {props.get('hs_lead_status', 'UNKNOWN')}",
        f"Lifecycle Stage: {props.get('lifecyclestage', 'UNKNOWN')}",
        f"Company: {props.get('company', 'N/A')}"
    ]
    
    return "\n".join(formatted)

@mcp.tool()
async def get_activities(contact_email: str, limit: int = 20) -> str:
    """Get recent activities (tasks, calls, meetings) for a contact."""
    # Find contact ID
    search_payload = {
        "filterGroups": [{
            "filters": [{
                "propertyName": "email",
                "operator": "EQ",
                "value": contact_email
            }]
        }]
    }
    
    search_result = await make_hubspot_request("POST", "/crm/v3/objects/contacts/search", data=search_payload)
    
    if "error" in search_result:
        return f"Error searching contact: {search_result.get('message', 'Unknown error')}"
    
    results = search_result.get("results", [])
    if not results:
        return f"Contact not found: {contact_email}"
    
    contact_id = results[0].get("id")
    
    activities = []
    
    # Fetch Tasks
    tasks = await fetch_batch_details(contact_id, "tasks", ["hs_task_subject", "hs_task_status", "hs_timestamp"])
    for task in tasks:
        props = task.get("properties", {})
        activities.append({
            "type": "TASK",
            "date": props.get("hs_timestamp", ""),
            "status": props.get("hs_task_status", "OPEN"),
            "summary": props.get("hs_task_subject", "No subject")
        })
    
    # Fetch Calls
    calls = await fetch_batch_details(contact_id, "calls", ["hs_call_title", "hs_call_status", "hs_timestamp"])
    for call in calls:
        props = call.get("properties", {})
        activities.append({
            "type": "CALL",
            "date": props.get("hs_timestamp", ""),
            "status": props.get("hs_call_status", "LOGGED"),
            "summary": props.get("hs_call_title", "No title")
        })
    
    # Fetch Meetings
    meetings = await fetch_batch_details(contact_id, "meetings", ["hs_meeting_title", "hs_meeting_outcome", "hs_meeting_start_time"])
    for meeting in meetings:
        props = meeting.get("properties", {})
        activities.append({
            "type": "MEETING",
            "date": props.get("hs_meeting_start_time", ""),
            "status": props.get("hs_meeting_outcome", "SCHEDULED"),
            "summary": props.get("hs_meeting_title", "No title")
        })
    
    # Sort by date descending
    activities.sort(key=lambda x: x.get("date", "0"), reverse=True)
    
    # Limit results
    activities = activities[:limit]
    
    if not activities:
        return f"No activities found for {contact_email}"
    
    formatted = [f"Found {len(activities)} activities for {contact_email}:"]
    for act in activities:
        date = act["date"][:10] if act["date"] else "N/A"
        formatted.append(
            f"{date} | {act['type']:<8} [{act['status']}] | {act['summary'][:50]}"
        )
    
    return "\n".join(formatted)

# === RESOURCES ===

@mcp.resource("hubspot://contacts/recent")
async def get_recent_contacts() -> str:
    """Get a list of recently updated contacts."""
    return await list_contacts(20)

if __name__ == "__main__":
    mcp.run()