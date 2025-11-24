import requests
import os
import time
import re
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MCP_HUBSPOT_URL = os.getenv("MCP_HUBSPOT_URL", "http://localhost:8001")
genai_client = genai.Client(api_key=GEMINI_API_KEY)

def call_mcp_tool(tool_name, args):
    try:
        endpoint = f"{MCP_HUBSPOT_URL}/tool/{tool_name}"
        data = {"limit": 20} if tool_name == "list_contacts" else \
               {"email": args} if tool_name == "get_contact_status" else \
               {"contact_email": args}
        response = requests.post(endpoint, json=data, timeout=20)
        return response.json() if response.ok else {"error": response.text}
    except Exception as e:
        return {"error": str(e)}

def call_gemini(prompt):
    try:
        config = types.GenerateContentConfig(temperature=0.1)
        resp = genai_client.models.generate_content(
            model="gemini-2.0-flash", 
            contents=f"You are a helper. Output ONLY tool: TOOL:list_contacts::limit\nUser: {prompt}", 
            config=config
        )
        return resp.text.strip() if resp.text else ""
    except:
        return ""

def main():
    print("Fetching contacts from HubSpot...")
    ai_resp = call_gemini("List all contacts")
    
    # Get list
    discovery = call_mcp_tool("list_contacts", "20")
    contacts = discovery.get("contacts", [])
    
    if not contacts:
        print("No contacts found.")
        return

    print(f"Found {len(contacts)} contacts. Analyzing...\n")
    
    for i, contact in enumerate(contacts, 1):
        email = contact['email']
        name = contact['name']
        
        print("-" * 70)
        print(f"{name} ({email})")
        
        # --- A. FETCH STATUS ---
        status_data = call_mcp_tool("get_contact_status", email)
        
        if status_data.get('contact_found'):
            # Extract the specific status you asked for
            lead_status = status_data.get('hs_lead_status')
            lifecycle = status_data.get('lifecyclestage')
            
            # Formatting Logic
            status_str = str(lead_status).upper() if lead_status else "UNKNOWN"
            print(f"Lead Status:    {status_str}")
            print(f"Lifecycle:      {str(lifecycle).upper()}")
        
        act_data = call_mcp_tool("get_activities", email)
        activities = act_data.get('activities', [])
        
        if activities:
            print(f"Recent History:")
            for act in activities[:5]:
                date = str(act.get('date', ''))[:10]
                a_type = act['type']
                a_status = act.get('status', '')
                summary = act.get('summary', '')
                
                # Clean up activity status display
                st_display = f"[{a_status}]" if a_status else ""
                
                print(f"{date} | {a_type:<8} {st_display:<15} | {summary[:35]}...")
        else:
            print("No recent activities.")
            
        time.sleep(0.2)

if __name__ == "__main__":
    main()