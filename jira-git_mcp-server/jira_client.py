import asyncio
import os
import sys
from typing import Optional, Dict, Any
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

load_dotenv()

class JiraMCPClient:
    def __init__(self):
        self.jira_url = os.getenv("JIRA_URL")
        self.jira_username = os.getenv("JIRA_USERNAME")
        self.jira_api_token = os.getenv("JIRA_API_TOKEN")
        
        if not all([self.jira_url, self.jira_username, self.jira_api_token]):
            raise ValueError("JIRA_URL/BASE_URL, JIRA_USERNAME, and JIRA_API_TOKEN are required.")
        
        self.session: Optional[ClientSession] = None

    async def connect(self):
        env = os.environ.copy()
        env["JIRA_BASE_URL"] = self.jira_url
        env["JIRA_USERNAME"] = self.jira_username
        env["JIRA_API_TOKEN"] = self.jira_api_token

        server_script = os.path.join(os.getcwd(), "jira_server.py")

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
        print("✓ Connected to Local Jira MCP Server")

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

    async def search_issues(self, jql: str, limit: int = 10):
        return await self.call_tool("search_issues", {
            "jql": jql, 
            "max_results": limit
        })

    async def get_assigned_issues(self, limit: int = 20):
        return await self.search_issues(
            jql="(assignee = currentUser() OR creator = currentUser()) ORDER BY created DESC",
            limit=limit
        )

    async def get_in_progress_issues(self, limit: int = 20):
        return await self.search_issues(
            jql="(assignee = currentUser() OR creator = currentUser()) AND statusCategory != Done ORDER BY updated DESC",
            limit=limit
        )
        
    async def get_project_issues(self, project_key: str = "KAN", limit: int = 50):
        return await self.search_issues(
            jql=f"project = {project_key} ORDER BY created DESC",
            limit=limit
        )

    async def get_all_projects(self):
        return await self.read_resource("jira://projects")

async def main():
    if not os.path.exists("server.py"):
        print("Error: server.py not found in current directory.")
        return

    async with JiraMCPClient() as client:
        print("\n" + "="*70)
        print("JIRA MCP CLIENT (TEXT MODE)")
        print("="*70)
        
        print("\n--- 1. YOUR PROJECTS ---")
        print(await client.get_all_projects())
        
        print("\n--- 2. ALL YOUR ASSIGNED TICKETS ---")
        print(await client.get_assigned_issues(limit=10))

        print("\n--- 3. YOUR IN-PROGRESS TICKETS ---")
        print(await client.get_in_progress_issues(limit=5))

if __name__ == "__main__":
    asyncio.run(main())