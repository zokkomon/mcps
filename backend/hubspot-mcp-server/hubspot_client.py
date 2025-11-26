import asyncio
import os
import sys
from typing import Optional, Dict, Any
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

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

    async def read_resource(self, uri: str) -> str:
        try:
            result = await self.session.read_resource(uri)
            if result and result.contents:
                return result.contents[0].text
            return "No content returned"
        except Exception as e:
            return f"Error reading resource {uri}: {str(e)}"

    # === Tool Wrappers ===

    async def list_contacts(self, limit: Optional[int] = None, fetch_all: bool = True):
        """
        List contacts from HubSpot.
        
        Args:
            limit: Maximum number of contacts to return (None = all)
            fetch_all: Whether to fetch all pages (pagination)
        """
        args = {"fetch_all": fetch_all}
        if limit is not None:
            args["limit"] = limit
        return await self.call_tool("list_contacts", args)

    async def list_contacts_by_date_range(self, start_date: str, end_date: str, limit: int = 100):
        """
        Get contacts created within a date range.
        
        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            limit: Maximum contacts to return
        """
        return await self.call_tool("list_contacts_by_date_range", {
            "start_date": start_date,
            "end_date": end_date,
            "limit": limit
        })

    async def get_contact_status(self, email: str):
        """Get the status and details of a contact."""
        return await self.call_tool("get_contact_status", {"email": email})

    async def get_activities(self, contact_email: str, limit: Optional[int] = None):
        """Get activities for a specific contact."""
        args = {"contact_email": contact_email}
        if limit is not None:
            args["limit"] = limit
        return await self.call_tool("get_activities", args)

    async def get_all_activities(self, limit_contacts: int = 10, limit_activities_per_contact: int = 50):
        """
        Get activities for multiple contacts.
        
        Args:
            limit_contacts: Number of contacts to fetch activities for
            limit_activities_per_contact: Max activities per contact
        """
        return await self.call_tool("get_all_activities", {
            "limit_contacts": limit_contacts,
            "limit_activities_per_contact": limit_activities_per_contact
        })

    async def get_recent_contacts_resource(self):
        """Get recent contacts using the resource URI."""
        return await self.read_resource("hubspot://contacts/recent")

    async def get_all_contacts_resource(self):
        """Get all contacts using the resource URI with pagination."""
        return await self.read_resource("hubspot://contacts/all")

async def main():
    if not os.path.exists("hubspot_server.py"):
        print("Error: hubspot_server.py not found in current directory.")
        return

    async with HubSpotMCPClient() as client:
        print("=" * 80)
        print("HUBSPOT MCP CLIENT - FIXED VERSION WITH PAGINATION")
        print("=" * 80)
        
        # 1. Fetch ALL contacts (with pagination)
        print("\n📋 FETCHING ALL CONTACTS (WITH PAGINATION)...")
        print("This may take a while if you have many contacts...")
        all_contacts = await client.list_contacts(limit=None, fetch_all=True)
        print(all_contacts)
        
        # 2. Fetch contacts from specific date range
        print("\n\n📅 FETCHING CONTACTS FROM LAST 7 DAYS...")
        from datetime import datetime, timedelta
        today = datetime.now()
        week_ago = today - timedelta(days=7)
        recent_contacts = await client.list_contacts_by_date_range(
            start_date=week_ago.strftime('%Y-%m-%d'),
            end_date=today.strftime('%Y-%m-%d'),
            limit=100
        )
        print(recent_contacts)
        
        # 3. Get contact details
        print("\n\n👤 FETCHING SPECIFIC CONTACT DETAILS...")
        # Extract first contact with email
        lines = all_contacts.split('\n')
        first_contact_email = None
        for line in lines:
            if '@' in line and '|' in line and 'Email' not in line:
                parts = line.split('|')
                if len(parts) >= 2:
                    email = parts[1].strip()
                    if email != "None":
                        first_contact_email = email
                        break
        
        if first_contact_email:
            status = await client.get_contact_status(first_contact_email)
            print(status)
            
            # 4. Get activities for specific contact
            print(f"\n\n📅 FETCHING ACTIVITIES FOR {first_contact_email}...")
            activities = await client.get_activities(first_contact_email, limit=100)
            print(activities)
        else:
            print("No contacts with email found.")
        
        # 5. Get activities for multiple contacts
        print("\n\n🔄 FETCHING ACTIVITIES FOR MULTIPLE CONTACTS (First 10)...")
        all_activities = await client.get_all_activities(
            limit_contacts=10,
            limit_activities_per_contact=50
        )
        print(all_activities)
        
        # 6. Use resources
        print("\n\n📦 FETCHING RECENT CONTACTS VIA RESOURCE...")
        recent_resource = await client.get_recent_contacts_resource()
        print(recent_resource)
        
        print("\n\n" + "=" * 80)
        print("✅ ALL OPERATIONS COMPLETED")
        print("=" * 80)

async def demo_specific_scenarios():
    """Demo specific use cases"""
    async with HubSpotMCPClient() as client:
        print("\n" + "=" * 80)
        print("DEMO: SPECIFIC SCENARIOS")
        print("=" * 80)
        
        # Scenario 1: Get exactly 250 contacts
        print("\n📊 Scenario 1: Fetch exactly 250 contacts")
        contacts_250 = await client.list_contacts(limit=250, fetch_all=True)
        print(contacts_250)
        
        # Scenario 2: Get contacts from March 2025
        print("\n📊 Scenario 2: Get contacts from March 2025")
        march_contacts = await client.list_contacts_by_date_range(
            start_date="2025-03-01",
            end_date="2025-03-31",
            limit=500
        )
        print(march_contacts)
        
        # Scenario 3: Get all activities for top 5 contacts
        print("\n📊 Scenario 3: Get activities for top 5 contacts")
        top_5_activities = await client.get_all_activities(
            limit_contacts=5,
            limit_activities_per_contact=100
        )
        print(top_5_activities)

if __name__ == "__main__":
    # Run main demo
    asyncio.run(main())
    
    # Uncomment to run specific scenarios
    # asyncio.run(demo_specific_scenarios())