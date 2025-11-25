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
        print("✓ Connected to Local HubSpot MCP Server")

    async def disconnect(self):
        if self.session:
            await self._session_context.__aexit__(None, None, None)
            await self._stdio_context.__aexit__(None, None, None)
            print("✓ Disconnected")

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

    async def list_contacts(self, limit: int = 20):
        """List recent contacts from HubSpot."""
        return await self.call_tool("list_contacts", {"limit": limit})

    async def get_contact_status(self, email: str):
        """Get the status and details of a contact."""
        return await self.call_tool("get_contact_status", {"email": email})

    async def get_activities(self, contact_email: str, limit: int = 20):
        """Get recent activities for a contact."""
        return await self.call_tool("get_activities", {
            "contact_email": contact_email,
            "limit": limit
        })

    async def get_recent_contacts_resource(self):
        """Get recent contacts using the resource URI."""
        return await self.read_resource("hubspot://contacts/recent")

async def main():
    if not os.path.exists("hubspot_server.py"):
        print("Error: hubspot_server.py not found in current directory.")
        return

    async with HubSpotMCPClient() as client:
        print("\n" + "="*70)
        print("HUBSPOT MCP CLIENT")
        print("="*70)
        
        print("\n--- 1. LIST RECENT CONTACTS ---")
        contacts_list = await client.list_contacts(limit=10)
        print(contacts_list)
        
        # Extract first email for demonstration
        lines = contacts_list.split('\n')
        first_contact_email = None
        for line in lines:
            if '@' in line and '|' in line:
                first_contact_email = line.split('|')[0].strip()
                break
        
        if first_contact_email:
            print(f"\n--- 2. GET CONTACT STATUS: {first_contact_email} ---")
            status = await client.get_contact_status(first_contact_email)
            print(status)
            
            print(f"\n--- 3. GET ACTIVITIES: {first_contact_email} ---")
            activities = await client.get_activities(first_contact_email, limit=5)
            print(activities)
        
        print("\n--- 4. RECENT CONTACTS (VIA RESOURCE) ---")
        recent = await client.get_recent_contacts_resource()
        print(recent)

if __name__ == "__main__":
    asyncio.run(main())