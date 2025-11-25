import asyncio
import os
import json
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

load_dotenv()

class GitHubMCPClient:
    def __init__(self):
        self.github_token = os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN")
        if not self.github_token:
            raise ValueError("GitHub token is required.")
        
        self.session: Optional[ClientSession] = None

    async def connect(self):
        server_params = StdioServerParameters(
            command="docker",
            args=[
                "run",
                "-i",
                "--rm",
                "-e", "GITHUB_PERSONAL_ACCESS_TOKEN",
                "ghcr.io/github/github-mcp-server"
            ],
            env=os.environ.copy()
        )

        self._stdio_context = stdio_client(server_params)
        self._read, self._write = await self._stdio_context.__aenter__()
        self._session_context = ClientSession(self._read, self._write)
        self.session = await self._session_context.__aenter__()
        await self.session.initialize()
        print("Connected to GitHub MCP Server")

    async def disconnect(self):
        if self.session:
            await self._session_context.__aexit__(None, None, None)
            await self._stdio_context.__aexit__(None, None, None)
            print("Disconnected")

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, *args):
        await self.disconnect()

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        try:
            return await self.session.call_tool(tool_name, arguments)
        except Exception as e:
            print(f"System Error calling {tool_name}: {e}")
            return None

    def safe_parse(self, result, source_name="Unknown"):
        if not result or not result.content:
            return None
        
        raw_text = result.content[0].text.strip()
        if not raw_text: return None

        try:
            return json.loads(raw_text)
        except json.JSONDecodeError:
            print(f"{source_name} returned text: \"{raw_text}\"")
            return raw_text

    async def get_current_user(self):
        result = await self.call_tool("get_me", {})
        return self.safe_parse(result, "get_me")

    async def list_issues(self, owner: str, repo: str):
        # FIXED: Changed "open" to "OPEN"
        result = await self.call_tool("list_issues", {
            "owner": owner, 
            "repo": repo,
            "state": "OPEN", 
            "per_page": 5
        })
        return self.safe_parse(result, "list_issues")

    async def list_commits(self, owner: str, repo: str):
        result = await self.call_tool("list_commits", {
            "owner": owner, 
            "repo": repo,
            "per_page": 5
        })
        return self.safe_parse(result, "list_commits")

async def main():
    TARGET_OWNER = "zokkomon" 
    TARGET_REPO = "mcps"

    async with GitHubMCPClient() as client:
        user = await client.get_current_user()
        if isinstance(user, dict):
            print(f"1. AUTH CHECK:{user.get('login')}")

        print(f"\n--- 2. ISSUES CHECK ({TARGET_OWNER}/{TARGET_REPO}) ---")
        issues = await client.list_issues(TARGET_OWNER, TARGET_REPO)
        
        if isinstance(issues, list):
            print(f"Found {len(issues)} issues.")
            for issue in issues:
                print(f"  2. ISSUES CHECK ({TARGET_OWNER}/{TARGET_REPO}) {issue.get('number')}: {issue.get('title')}")
        elif isinstance(issues, str):
            print(f"Server Message: {issues}")
        else:
            print("No open issues found.\n")

        commits = await client.list_commits(TARGET_OWNER, TARGET_REPO)
        if isinstance(commits, list):
            for c in commits:
                msg = c.get('commit', {}).get('message', '').split('\n')[0]
                print(f" 3. COMMITS CHECK:{msg[:50]}...")

if __name__ == "__main__":
    asyncio.run(main())