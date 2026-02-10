import asyncio
import json
import os
from typing import Optional, Dict, Any
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
        print(f"Connecting to MCP server... (PID: {os.getpid()})")
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
        print("Connected to GitHub MCP Server\n")

    async def disconnect(self):
        if self.session:
            await self._session_context.__aexit__(None, None, None)
            await self._stdio_context.__aexit__(None, None, None)
            print("\nDisconnected")

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, *args):
        await self.disconnect()

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        try:
            return await self.session.call_tool(tool_name, arguments)
        except Exception as e:
            print(f"Error calling {tool_name}: {e}")
            return None

    def safe_parse(self, result, source_name="Unknown"):
        if not result or not result.content:
            return None
        raw_text = result.content[0].text.strip()
        if not raw_text: 
            return None
        try:
            return json.loads(raw_text)
        except json.JSONDecodeError:
            return raw_text

    async def get_current_user(self):
        result = await self.call_tool("get_me", {})
        return self.safe_parse(result, "get_me")

    async def list_issues(self, owner: str, repo: str):
        result = await self.call_tool("list_issues", {
            "owner": owner, 
            "repo": repo,
            "state": "OPEN", 
            "perPage": 5
        })
        return self.safe_parse(result, "list_issues")

    async def search_repos(self, org_name: str):
        all_repos = []
        page = 1
        
        while True:
            result = await self.call_tool("search_repositories", {
                "query": f"org:{org_name}",
                "minimal_output": True,
                "perPage": 100,
                "page": page
            })
            
            data = self.safe_parse(result, "search_repositories")
            
            if not data or "items" not in data or len(data["items"]) == 0:
                break
            
            all_repos.extend(data["items"])
            
            # Check if we've retrieved all repositories
            total_count = data.get("total_count", 0)
            if len(all_repos) >= total_count:
                break
            
            page += 1
            await asyncio.sleep(0.2)          
        return {"items": all_repos, "total_count": len(all_repos)}


async def main():
    print(f"main() called in PID {os.getpid()}\n")
    
    try:
        async with GitHubMCPClient() as client:
            user = await client.get_current_user()
            username = user.get("login")
            print(f"Authenticated as: {username}\n")
            orgname = 'InfiniumDevIO'
            
            print("Fetching all repositories...")
            repos = await client.search_repos(orgname)
            
            if repos and "items" in repos:
                total = len(repos["items"])
                print(f"Found {total} repos\n")
                
                for i, repo in enumerate(repos["items"], 1):
                    try:
                        full_name = repo["full_name"]
                        owner, name = full_name.split("/")
                        visibility = "Private" if repo.get("private") else "Public"
                        
                        print(f"[{i}/{total}] {owner}/{name} - {visibility}")
                        
                        issues = await client.list_issues(owner, name)
                        if issues and isinstance(issues, list) and len(issues) > 0:
                            print(f"  └─ {len(issues)} open issues")
                        
                        await asyncio.sleep(0.2)
                        
                    except Exception as e:
                        print(f"[{i}/{total}] Error: {e}")
                
                print(f"\nProcessed all {total} repositories")
            else:
                print("No repositories found")
                
    except Exception as e:
        print(f"\nFatal error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())