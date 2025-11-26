import sys
import os
import httpx
from typing import Dict, Optional, List
from mcp.server.fastmcp import FastMCP
from datetime import datetime
from collections import defaultdict

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
    
    async with httpx.AsyncClient(timeout=30.0) as client:
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
    
    if not ids:
        return []
    
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
async def list_contacts(limit: Optional[int] = None, fetch_all: bool = True) -> str:
    """
    List contacts from HubSpot with pagination support.
    
    Args:
        limit: Maximum number of contacts to return (None = all contacts)
        fetch_all: If True, fetches all pages. If False, only first page.
    """
    all_contacts = []
    after = None
    page_limit = 100  # Max per HubSpot API
    
    while True:
        params = {
            "limit": page_limit,
            "properties": ["email", "firstname", "lastname", "hs_lead_status", "lifecyclestage", "company", "createdate"],
            "sort": "-createdate"
        }
        
        if after:
            params["after"] = after
        
        result = await make_hubspot_request("GET", "/crm/v3/objects/contacts", params=params)
        
        if "error" in result:
            return f"Error listing contacts: {result.get('message', 'Unknown error')}"
        
        page_results = result.get("results", [])
        all_contacts.extend(page_results)
        
        # Check if there are more pages
        paging = result.get("paging", {})
        after = paging.get("next", {}).get("after")
        
        # Stop conditions
        if not after or not fetch_all:
            break
        
        if limit and len(all_contacts) >= limit:
            break
    
    # Apply limit if specified
    if limit:
        all_contacts = all_contacts[:limit]
    
    # Process contacts
    contacts = []
    date_counts = defaultdict(int)
    
    for res in all_contacts:
        props = res.get("properties", {})
        email = props.get("email") or "None"
        firstname = props.get("firstname", "")
        lastname = props.get("lastname", "")
        name = f"{firstname} {lastname}".strip() or "N/A"
        lead_status = props.get("hs_lead_status") or "None"
        lifecycle_stage = props.get("lifecyclestage") or "None"
        company = props.get("company") or "N/A"
        createdate = props.get("createdate", "N/A")
        
        # Parse date for counting
        if createdate != "N/A":
            try:
                date_obj = datetime.fromisoformat(createdate.replace('Z', '+00:00'))
                date_key = date_obj.strftime('%Y-%m-%d')
                date_counts[date_key] += 1
            except:
                pass
        
        contacts.append({
            "name": name,
            "email": email,
            "lead_status": lead_status,
            "lifecycle_stage": lifecycle_stage,
            "company": company,
            "createdate": createdate
        })
    
    if not contacts:
        return "No contacts found."
    
    # Build structured output
    output = []
    output.append("=== CONTACTS LIST ===")
    output.append(f"Total Contacts: {len(contacts)}")
    output.append("")
    output.append("Contact Name | Email | Lead Status | Lifecycle Stage | Company | Created Date")
    output.append("-" * 120)
    
    for contact in contacts:
        output.append(f"{contact['name']:<25} | {contact['email']:<35} | {contact['lead_status']:<12} | {contact['lifecycle_stage']:<18} | {contact['company']:<25} | {contact['createdate']}")
    
    # Add datewise summary
    output.append("")
    output.append("=== LEADS ADDED BY DATE ===")
    output.append(f"Total Unique Dates: {len(date_counts)}")
    output.append("")
    output.append("Date       | Lead Count")
    output.append("-" * 30)
    
    for date in sorted(date_counts.keys(), reverse=True):
        output.append(f"{date} | {date_counts[date]}")
    
    return "\n".join(output)

@mcp.tool()
async def list_contacts_by_date_range(start_date: str, end_date: str, limit: int = 100) -> str:
    """
    List contacts created within a date range.
    
    Args:
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        limit: Maximum number of contacts to return
    """
    payload = {
        "limit": limit,
        "properties": ["email", "firstname", "lastname", "hs_lead_status", "lifecyclestage", "company", "createdate"],
        "sorts": [{"propertyName": "createdate", "direction": "DESCENDING"}],
        "filterGroups": [{
            "filters": [
                {
                    "propertyName": "createdate",
                    "operator": "GTE",
                    "value": f"{start_date}T00:00:00.000Z"
                },
                {
                    "propertyName": "createdate",
                    "operator": "LTE",
                    "value": f"{end_date}T23:59:59.999Z"
                }
            ]
        }]
    }
    
    result = await make_hubspot_request("POST", "/crm/v3/objects/contacts/search", data=payload)
    
    if "error" in result:
        return f"Error searching contacts: {result.get('message', 'Unknown error')}"
    
    contacts = []
    date_counts = defaultdict(int)
    
    for res in result.get("results", []):
        props = res.get("properties", {})
        email = props.get("email") or "None"
        firstname = props.get("firstname", "")
        lastname = props.get("lastname", "")
        name = f"{firstname} {lastname}".strip() or "N/A"
        lead_status = props.get("hs_lead_status") or "None"
        lifecycle_stage = props.get("lifecyclestage") or "None"
        company = props.get("company") or "N/A"
        createdate = props.get("createdate", "N/A")
        
        if createdate != "N/A":
            try:
                date_obj = datetime.fromisoformat(createdate.replace('Z', '+00:00'))
                date_key = date_obj.strftime('%Y-%m-%d')
                date_counts[date_key] += 1
            except:
                pass
        
        contacts.append({
            "name": name,
            "email": email,
            "lead_status": lead_status,
            "lifecycle_stage": lifecycle_stage,
            "company": company,
            "createdate": createdate
        })
    
    if not contacts:
        return f"No contacts found between {start_date} and {end_date}"
    
    # Build output
    output = []
    output.append(f"=== CONTACTS FROM {start_date} TO {end_date} ===")
    output.append(f"Total Contacts: {len(contacts)}")
    output.append("")
    output.append("Contact Name | Email | Lead Status | Lifecycle Stage | Company | Created Date")
    output.append("-" * 120)
    
    for contact in contacts:
        output.append(f"{contact['name']:<25} | {contact['email']:<35} | {contact['lead_status']:<12} | {contact['lifecycle_stage']:<18} | {contact['company']:<25} | {contact['createdate']}")
    
    output.append("")
    output.append("=== LEADS ADDED BY DATE ===")
    output.append(f"Total Unique Dates: {len(date_counts)}")
    output.append("")
    output.append("Date       | Lead Count")
    output.append("-" * 30)
    
    for date in sorted(date_counts.keys(), reverse=True):
        output.append(f"{date} | {date_counts[date]}")
    
    return "\n".join(output)

@mcp.tool()
async def get_contact_status(email: str) -> str:
    """Get the status and details of a contact by email."""
    payload = {
        "limit": 1,
        "properties": ["firstname", "lastname", "email", "lifecyclestage", "hs_lead_status", "company", "createdate"],
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
    
    output = []
    output.append("=== CONTACT DETAILS ===")
    output.append(f"Name: {props.get('firstname', '')} {props.get('lastname', '')}")
    output.append(f"Email: {props.get('email', 'N/A')}")
    output.append(f"Lead Status: {props.get('hs_lead_status') or 'None'}")
    output.append(f"Lifecycle Stage: {props.get('lifecyclestage') or 'None'}")
    output.append(f"Company: {props.get('company') or 'N/A'}")
    output.append(f"Created Date: {props.get('createdate', 'N/A')}")
    
    return "\n".join(output)

@mcp.tool()
async def get_activities(contact_email: str, limit: int = 100) -> str:
    """Get activities for a contact with datewise summary."""
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
    date_counts = defaultdict(int)
    
    # Fetch Tasks
    tasks = await fetch_batch_details(contact_id, "tasks", ["hs_task_subject", "hs_task_status", "hs_timestamp"])
    for task in tasks:
        props = task.get("properties", {})
        timestamp = props.get("hs_timestamp", "")
        date_str = timestamp[:10] if timestamp else "N/A"
        
        if date_str != "N/A":
            date_counts[date_str] += 1
        
        activities.append({
            "type": "TASK",
            "date": date_str,
            "status": props.get("hs_task_status", "OPEN"),
            "summary": props.get("hs_task_subject", "No subject")
        })
    
    # Fetch Calls
    calls = await fetch_batch_details(contact_id, "calls", ["hs_call_title", "hs_call_status", "hs_timestamp"])
    for call in calls:
        props = call.get("properties", {})
        timestamp = props.get("hs_timestamp", "")
        date_str = timestamp[:10] if timestamp else "N/A"
        
        if date_str != "N/A":
            date_counts[date_str] += 1
        
        activities.append({
            "type": "CALL",
            "date": date_str,
            "status": props.get("hs_call_status", "COMPLETED"),
            "summary": props.get("hs_call_title", "No title")
        })
    
    # Fetch Meetings
    meetings = await fetch_batch_details(contact_id, "meetings", ["hs_meeting_title", "hs_meeting_outcome", "hs_meeting_start_time"])
    for meeting in meetings:
        props = meeting.get("properties", {})
        timestamp = props.get("hs_meeting_start_time", "")
        date_str = timestamp[:10] if timestamp else "N/A"
        
        if date_str != "N/A":
            date_counts[date_str] += 1
        
        activities.append({
            "type": "MEETING",
            "date": date_str,
            "status": props.get("hs_meeting_outcome", "SCHEDULED"),
            "summary": props.get("hs_meeting_title", "No title")
        })
    
    # Sort by date descending
    activities.sort(key=lambda x: x.get("date", "0"), reverse=True)
    
    # Limit results
    activities = activities[:limit]
    
    if not activities:
        return f"No activities found for {contact_email}"
    
    # Build structured output
    output = []
    output.append(f"=== ACTIVITIES FOR {contact_email} ===")
    output.append(f"Total Activities: {len(activities)}")
    output.append("")
    output.append("Date       | Type     | Status      | Summary")
    output.append("-" * 100)
    
    for act in activities:
        date = act["date"] if act["date"] != "N/A" else "N/A      "
        activity_type = act["type"]
        status = act["status"]
        summary = act["summary"][:60]  # Truncate long summaries
        
        output.append(f"{date} | {activity_type:<8} | {status:<11} | {summary}")
    
    # Add datewise summary
    output.append("")
    output.append("=== ACTIVITIES BY DATE ===")
    output.append(f"Total Unique Dates: {len(date_counts)}")
    output.append("")
    output.append("Date       | Activity Count")
    output.append("-" * 30)
    
    for date in sorted(date_counts.keys(), reverse=True):
        output.append(f"{date} | {date_counts[date]}")
    
    return "\n".join(output)

@mcp.tool()
async def get_all_activities(limit_contacts: int = 10, limit_activities_per_contact: int = 50) -> str:
    """
    Get activities for multiple contacts.
    
    Args:
        limit_contacts: Number of contacts to fetch activities for
        limit_activities_per_contact: Max activities per contact
    """
    # Get contacts
    contacts_result = await make_hubspot_request(
        "GET", 
        "/crm/v3/objects/contacts",
        params={
            "limit": limit_contacts,
            "properties": ["email", "firstname", "lastname"],
            "sort": "-createdate"
        }
    )
    
    if "error" in contacts_result:
        return f"Error fetching contacts: {contacts_result.get('message', 'Unknown error')}"
    
    all_activities = []
    date_counts = defaultdict(int)
    contact_activity_counts = defaultdict(int)
    
    for contact in contacts_result.get("results", []):
        contact_id = contact.get("id")
        props = contact.get("properties", {})
        email = props.get("email") or "N/A"
        firstname = props.get("firstname", "")
        lastname = props.get("lastname", "")
        name = f"{firstname} {lastname}".strip() or "N/A"
        
        # Fetch activities for this contact
        tasks = await fetch_batch_details(contact_id, "tasks", ["hs_task_subject", "hs_task_status", "hs_timestamp"])
        calls = await fetch_batch_details(contact_id, "calls", ["hs_call_title", "hs_call_status", "hs_timestamp"])
        meetings = await fetch_batch_details(contact_id, "meetings", ["hs_meeting_title", "hs_meeting_outcome", "hs_meeting_start_time"])
        
        for task in tasks:
            props_t = task.get("properties", {})
            timestamp = props_t.get("hs_timestamp", "")
            date_str = timestamp[:10] if timestamp else "N/A"
            
            if date_str != "N/A":
                date_counts[date_str] += 1
            contact_activity_counts[name] += 1
            
            all_activities.append({
                "contact": name,
                "email": email,
                "type": "TASK",
                "date": date_str,
                "status": props_t.get("hs_task_status", "OPEN"),
                "summary": props_t.get("hs_task_subject", "No subject")
            })
        
        for call in calls:
            props_c = call.get("properties", {})
            timestamp = props_c.get("hs_timestamp", "")
            date_str = timestamp[:10] if timestamp else "N/A"
            
            if date_str != "N/A":
                date_counts[date_str] += 1
            contact_activity_counts[name] += 1
            
            all_activities.append({
                "contact": name,
                "email": email,
                "type": "CALL",
                "date": date_str,
                "status": props_c.get("hs_call_status", "COMPLETED"),
                "summary": props_c.get("hs_call_title", "No title")
            })
        
        for meeting in meetings:
            props_m = meeting.get("properties", {})
            timestamp = props_m.get("hs_meeting_start_time", "")
            date_str = timestamp[:10] if timestamp else "N/A"
            
            if date_str != "N/A":
                date_counts[date_str] += 1
            contact_activity_counts[name] += 1
            
            all_activities.append({
                "contact": name,
                "email": email,
                "type": "MEETING",
                "date": date_str,
                "status": props_m.get("hs_meeting_outcome", "SCHEDULED"),
                "summary": props_m.get("hs_meeting_title", "No title")
            })
    
    if not all_activities:
        return f"No activities found for the first {limit_contacts} contacts"
    
    # Sort by date descending
    all_activities.sort(key=lambda x: x.get("date", "0"), reverse=True)
    
    # Build output
    output = []
    output.append(f"=== ALL ACTIVITIES (First {limit_contacts} Contacts) ===")
    output.append(f"Total Activities: {len(all_activities)}")
    output.append("")
    output.append("Contact Name | Email | Type | Date | Status | Summary")
    output.append("-" * 120)
    
    for act in all_activities[:limit_activities_per_contact * limit_contacts]:
        output.append(f"{act['contact']:<20} | {act['email']:<25} | {act['type']:<8} | {act['date']} | {act['status']:<11} | {act['summary'][:40]}")
    
    # Add summary by contact
    output.append("")
    output.append("=== ACTIVITIES BY CONTACT ===")
    output.append("")
    output.append("Contact Name | Activity Count")
    output.append("-" * 40)
    
    for contact in sorted(contact_activity_counts.keys()):
        output.append(f"{contact:<20} | {contact_activity_counts[contact]}")
    
    # Add datewise summary
    output.append("")
    output.append("=== ACTIVITIES BY DATE ===")
    output.append(f"Total Unique Dates: {len(date_counts)}")
    output.append("")
    output.append("Date       | Activity Count")
    output.append("-" * 30)
    
    for date in sorted(date_counts.keys(), reverse=True):
        output.append(f"{date} | {date_counts[date]}")
    
    return "\n".join(output)

# === RESOURCES ===

@mcp.resource("hubspot://contacts/recent")
async def get_recent_contacts() -> str:
    """Get a list of recently updated contacts."""
    return await list_contacts(limit=20, fetch_all=False)

@mcp.resource("hubspot://contacts/all")
async def get_all_contacts() -> str:
    """Get all contacts with pagination."""
    return await list_contacts(limit=None, fetch_all=True)

if __name__ == "__main__":
    mcp.run()