import asyncio
import os
import sys
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from datetime import datetime, timedelta

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

        server_script = os.path.join(os.getcwd(), "hubspot_server.py")

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
        return await self.call_tool("list_contacts_by_date_range", {
            "start_date": start_date,
            "end_date": end_date,
            "limit": limit
        })

    async def get_recent_activities_by_date(self, start_date: str, end_date: str, limit_contacts: int = 50):
        """Get activities for contacts created within a specific date range."""
        return await self.call_tool("get_recent_activities_by_date", {
            "start_date": start_date,
            "end_date": end_date,
            "limit_contacts": limit_contacts
        })

async def main():
    """Main function - focuses ONLY on recent contacts and their activities"""
    if not os.path.exists("hubspot_server.py"):
        print("Error: hubspot_server.py not found in current directory.")
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
        contacts_30d = await client.list_contacts_by_date_range(
            start_date=days_30.strftime('%Y-%m-%d'),
            end_date=today.strftime('%Y-%m-%d'),
            limit=200  # Changed from 500 to 200 (HubSpot max)
        )
        print(contacts_30d)
        
        # 2. Get activities for contacts created in last 30 days
        print("\n\n📞 STEP 2: ACTIVITIES FOR CONTACTS FROM LAST 30 DAYS")
        print("-" * 80)
        activities_30d = await client.get_recent_activities_by_date(
            start_date=days_30.strftime('%Y-%m-%d'),
            end_date=today.strftime('%Y-%m-%d'),
            limit_contacts=100
        )
        print(activities_30d)
        
        print("\n\n" + "=" * 80)
        print("✅ REPORT COMPLETED")
        print("- Last 30 days: Contacts and their activities")

async def custom_date_report():
    """Generate report for specific date ranges"""
    async with HubSpotMCPClient() as client:
        print("\n" + "=" * 80)
        print("CUSTOM DATE RANGE REPORT")
        print("=" * 80)
        
        # September 2025 contacts
        print("\n📅 CONTACTS FROM SEPTEMBER 2025")
        sep_contacts = await client.list_contacts_by_date_range(
            start_date="2025-09-01",
            end_date="2025-09-30",
            limit=200 
        )
        print(sep_contacts)
        
        print("\n📞 ACTIVITIES FOR SEPTEMBER 2025 CONTACTS")
        sep_activities = await client.get_recent_activities_by_date(
            start_date="2025-09-01",
            end_date="2025-09-30",
            limit_contacts=100
        )
        print(sep_activities)
        
        # October 2025 contacts
        print("\n\n📅 CONTACTS FROM OCTOBER 2025")
        oct_contacts = await client.list_contacts_by_date_range(
            start_date="2025-10-01",
            end_date="2025-10-31",
            limit=200  # Changed from 500 to 200
        )
        print(oct_contacts)
        
        print("\n📞 ACTIVITIES FOR OCTOBER 2025 CONTACTS")
        oct_activities = await client.get_recent_activities_by_date(
            start_date="2025-10-01",
            end_date="2025-10-31",
            limit_contacts=100
        )
        print(oct_activities)
        
        # November 2025 contacts
        print("\n\n📅 CONTACTS FROM NOVEMBER 2025")
        nov_contacts = await client.list_contacts_by_date_range(
            start_date="2025-11-01",
            end_date="2025-11-30",
            limit=200  
        )
        print(nov_contacts)
        
        print("\n📞 ACTIVITIES FOR NOVEMBER 2025 CONTACTS")
        nov_activities = await client.get_recent_activities_by_date(
            start_date="2025-11-01",
            end_date="2025-11-30",
            limit_contacts=100
        )
        print(nov_activities)

if __name__ == "__main__":
    asyncio.run(main())
    
    # Uncomment to run custom date report (Sep, Oct, Nov 2025)
    # asyncio.run(custom_date_report())