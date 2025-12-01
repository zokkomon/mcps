import asyncio
import os
import sys
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from datetime import datetime, timedelta
import json

load_dotenv()

class HubSpotMCPClient:
    def __init__(self):
        self.hubspot_api_key = os.getenv("HUBSPOT_API_KEY")
        
        if not self.hubspot_api_key:
            raise ValueError("HUBSPOT_API_KEY is required.")
        
        self.session: Optional[ClientSession] = None

    async def connect(self):
        env = os.environ.copy()
        env["HUBSPOT_API_KEY"] = self.hubspot_api_key

        server_script = os.path.join(os.getcwd(), "hubspot-mcp-server", "hubspot_server.py")

        server_params = StdioServerParameters(
            command=sys.executable,
            args=[server_script],
            env=env
        )

        self._stdio_context = stdio_client(server_params)
        self._read, self._write = await self._stdio_context.__aenter__()
        self._session_context = ClientSession(self._read, self._write)
        self.session = await self._session_context.__aenter__()
        await self.session.initialize()
        print("✓ Connected to Local HubSpot MCP Server\n")

    async def disconnect(self):
        if self.session:
            await self._session_context.__aexit__(None, None, None)
            await self._stdio_context.__aexit__(None, None, None)
            print("\n✓ Disconnected")

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, *args):
        await self.disconnect()

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        try:
            result = await self.session.call_tool(tool_name, arguments)
            if result and result.content:
                return result.content[0].text
            return "No content returned"
        except Exception as e:
            return f"Error calling tool {tool_name}: {str(e)}"

    # === Tool Wrappers ===

    async def list_contacts_by_date_range(self, start_date: str, end_date: str, limit: int = 100):
        """Get contacts created within a date range."""
        result = await self.call_tool("list_contacts_by_date_range", {
            "start_date": start_date,
            "end_date": end_date,
            "limit": limit
        })
        return self._parse_contacts_response(result)

    async def get_recent_activities_by_date(self, start_date: str, end_date: str, limit_contacts: int = 50):
        """Get activities for contacts created within a specific date range."""
        try:
            result = await self.call_tool("get_recent_activities_by_date", {
                "start_date": start_date,
                "end_date": end_date,
                "limit_contacts": limit_contacts
            })
            return self._parse_activities_response(result)
        except Exception as e:
            print(f"Error fetching activities: {e}")
            return {
                "error": str(e),
                "activities": []
            }

    def _parse_contacts_response(self, response: str) -> Dict[str, Any]:
        """Parse the contacts response into structured data"""
        try:
            lines = response.strip().split('\n')
            contacts = []
            leads_by_date = {}
            
            # Parse contacts
            in_contacts_section = False
            for line in lines:
                if 'Contact Name' in line and 'Email' in line:
                    in_contacts_section = True
                    continue
                
                if in_contacts_section and '|' in line and '---' not in line:
                    parts = [p.strip() for p in line.split('|')]
                    if len(parts) >= 6:
                        contact = {
                            'name': parts[0],
                            'email': parts[1],
                            'lead_status': parts[2],
                            'lifecycle_stage': parts[3],
                            'company': parts[4],
                            'created_date': parts[5]
                        }
                        contacts.append(contact)
                        
                        # Track by date
                        date = parts[5].split()[0] if parts[5] else 'Unknown'
                        leads_by_date[date] = leads_by_date.get(date, 0) + 1
                
                if '=== LEADS ADDED BY DATE ===' in line:
                    in_contacts_section = False
            
            # Parse leads by date from the report section
            in_leads_section = False
            for line in lines:
                if 'Date       | Lead Count' in line:
                    in_leads_section = True
                    continue
                if in_leads_section and '|' in line and '---' not in line and line.strip():
                    parts = [p.strip() for p in line.split('|')]
                    if len(parts) >= 2:
                        try:
                            date = parts[0]
                            count = int(parts[1])
                            leads_by_date[date] = count
                        except:
                            pass
            
            # Sort leads by date descending
            sorted_leads = sorted(leads_by_date.items(), key=lambda x: x[0], reverse=True)
            
            return {
                'contacts': contacts,
                'total_contacts': len(contacts),
                'leads_by_date': sorted_leads,
                'raw_response': response
            }
        except Exception as e:
            print(f"Error parsing contacts: {e}")
            return {
                'contacts': [],
                'total_contacts': 0,
                'leads_by_date': [],
                'raw_response': response
            }

    def _parse_activities_response(self, response: str) -> Dict[str, Any]:
        """Parse the activities response into structured data"""
        try:
            if not response or response == "No content returned":
                return {
                    "error": "No activities data available",
                    "activities": []
                }
            
            lines = response.strip().split('\n')
            activities = []
            
            current_contact = None
            for line in lines:
                if '===' in line and 'CONTACT:' in line:
                    # Extract contact name
                    current_contact = line.split('CONTACT:')[1].split('===')[0].strip()
                elif current_contact and '|' in line and '---' not in line:
                    parts = [p.strip() for p in line.split('|')]
                    if len(parts) >= 4:
                        activities.append({
                            'contact': current_contact,
                            'type': parts[0],
                            'subject': parts[1],
                            'timestamp': parts[2],
                            'details': parts[3] if len(parts) > 3 else ''
                        })
            
            return {
                'activities': activities,
                'total_activities': len(activities),
                'raw_response': response
            }
        except Exception as e:
            print(f"Error parsing activities: {e}")
            return {
                'error': str(e),
                'activities': [],
                'raw_response': response
            }


async def main():
    """Main function - focuses ONLY on recent contacts and their activities"""
    if not os.path.exists("hubspot-mcp-server/hubspot_server.py"):
        print("Error: hubspot_server.py not found.")
        return

    async with HubSpotMCPClient() as client:
        print("=" * 80)
        print("HUBSPOT RECENT CONTACTS & ACTIVITIES REPORT")
        print("=" * 80)
        
        today = datetime.now()
        
        # 1. Get contacts from last 30 days
        print("\n📅 STEP 1: CONTACTS FROM LAST 30 DAYS")
        print("-" * 80)
        days_30 = today - timedelta(days=30)
        contacts_data = await client.list_contacts_by_date_range(
            start_date=days_30.strftime('%Y-%m-%d'),
            end_date=today.strftime('%Y-%m-%d'),
            limit=200 
        )
        print(json.dumps(contacts_data, indent=2))
        
        # 2. Get activities for contacts created in last 30 days
        print("\n\n📞 STEP 2: ACTIVITIES FOR CONTACTS FROM LAST 30 DAYS")
        print("-" * 80)
        activities_data = await client.get_recent_activities_by_date(
            start_date=days_30.strftime('%Y-%m-%d'),
            end_date=today.strftime('%Y-%m-%d'),
            limit_contacts=100
        )
        print(json.dumps(activities_data, indent=2))


if __name__ == "__main__":
    asyncio.run(main())