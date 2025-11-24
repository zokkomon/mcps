import sys
import os
import httpx
from typing import Dict, Optional
from mcp.server.fastmcp import FastMCP

# Create an MCP server
mcp = FastMCP("Jira MCP")

# Environment variables
JIRA_BASE_URL = os.environ.get("JIRA_BASE_URL")
JIRA_USERNAME = os.environ.get("JIRA_USERNAME")
JIRA_API_TOKEN = os.environ.get("JIRA_API_TOKEN")

if not all([JIRA_BASE_URL, JIRA_USERNAME, JIRA_API_TOKEN]):
    print("Warning: Jira environment variables not fully configured.", file=sys.stderr)

def get_headers():
    import base64
    base_url = JIRA_BASE_URL.rstrip('/') if JIRA_BASE_URL else ""
    auth_str = f"{JIRA_USERNAME}:{JIRA_API_TOKEN}"
    auth_bytes = auth_str.encode("ascii")
    auth_b64 = base64.b64encode(auth_bytes).decode("ascii")
    return {
        "Authorization": f"Basic {auth_b64}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }, base_url

async def make_jira_request(method: str, endpoint: str, data: Dict = None) -> Dict:
    headers, base_url = get_headers()
    url = f"{base_url}{endpoint}"
    
    async with httpx.AsyncClient() as client:
        response = await client.request(method, url, headers=headers, json=data)
        
        if response.status_code >= 400:
            print(f"Jira API Error {response.status_code}: {response.text}", file=sys.stderr)
            return {
                "error": True,
                "status_code": response.status_code,
                "message": response.text
            }
            
        return response.json()

# === TOOLS ===

@mcp.tool()
async def get_issue(issue_key: str) -> str:
    """Get details of a specific Jira issue."""
    result = await make_jira_request("GET", f"/rest/api/3/issue/{issue_key}")
    
    if "error" in result:
        return f"Error retrieving issue: {result.get('message', 'Unknown error')}"
    
    fields = result.get("fields", {})
    formatted = [
        f"Issue: {result.get('key', 'Unknown')}",
        f"Summary: {fields.get('summary', 'No summary')}",
        f"Status: {fields.get('status', {}).get('name', 'Unknown')}",
        f"Type: {fields.get('issuetype', {}).get('name', 'Unknown')}",
        f"Assignee: {fields.get('assignee', {}).get('displayName', 'Unassigned')}",
        "\nDescription:",
        fields.get('description', {}).get('text', 'No text description') if isinstance(fields.get('description'), dict) else str(fields.get('description', 'No description'))
    ]
    return "\n".join(formatted)

@mcp.tool()
async def search_issues(jql: str, max_results: int = 10) -> str:
    """Search for Jira issues using JQL."""
    data = {
        "jql": jql,
        "maxResults": max_results,
        "fields": ["key", "summary", "status", "issuetype", "priority", "assignee"]
    }
    
    result = await make_jira_request("POST", "/rest/api/3/search/jql", data)
    
    if "error" in result:
        return f"Error searching issues: {result.get('message', 'Unknown error')}"
    
    issues = result.get("issues", [])
    if not issues:
        return "No issues found matching the query."
    
    formatted = [f"Found {len(issues)} issues:"]
    for issue in issues:
        fields = issue.get("fields", {})
        status = fields.get("status", {}).get("name", "Unknown")
        assignee = fields.get("assignee", {}).get("displayName", "Unassigned")
        formatted.append(
            f"{issue.get('key')}: {fields.get('summary', 'No summary')} [{status}] ({assignee})"
        )
    
    return "\n".join(formatted)

def to_adf(text: str) -> Dict:
    """Converts simple text to Atlassian Document Format (ADF) for API v3."""
    if not text:
        return None
    return {
        "type": "doc",
        "version": 1,
        "content": [
            {
                "type": "paragraph",
                "content": [
                    {
                        "type": "text",
                        "text": text
                    }
                ]
            }
        ]
    }

@mcp.tool()
async def create_issue(project_key: str, summary: str, description: str, issue_type: str = "Task") -> str:
    """Create a new Jira issue (API v3)."""
    data = {
        "fields": {
            "project": {"key": project_key},
            "summary": summary,
            "description": to_adf(description), 
            "issuetype": {"name": issue_type}
        }
    }
    result = await make_jira_request("POST", "/rest/api/3/issue", data)
    
    if "error" in result:
        return f"Error creating issue: {result.get('message', result)}"
    return f"Issue created: {result.get('key')}"

@mcp.tool()
async def update_issue(issue_key: str, summary: Optional[str] = None) -> str:
    """Update an existing Jira issue (API v3)."""
    fields = {}
    if summary:
        fields["summary"] = summary
    
    if not fields:
        return "No fields provided."
    
    result = await make_jira_request("PUT", f"/rest/api/3/issue/{issue_key}", {"fields": fields})
    
    if "error" in result:
        return f"Error: {result.get('message', result)}"
    return f"Issue {issue_key} updated."

@mcp.tool()
async def add_comment(issue_key: str, comment: str) -> str:
    """Add a comment to a Jira issue (API v3)."""
    data = {
        "body": to_adf(comment) 
    }
    
    # Updated to api/3
    result = await make_jira_request("POST", f"/rest/api/3/issue/{issue_key}/comment", data)
    
    if "error" in result:
        return f"Error: {result.get('message', result)}"
    return f"Comment added to {issue_key}."

@mcp.tool()
async def transition_issue(issue_key: str, transition_name: str) -> str:
    """Transition an issue to a new status (API v3)."""
    t_result = await make_jira_request("GET", f"/rest/api/3/issue/{issue_key}/transitions")
    
    if "error" in t_result:
        return f"Error fetching transitions: {t_result.get('message')}"
    
    t_id = next((t['id'] for t in t_result.get('transitions', []) if t['name'].lower() == transition_name.lower()), None)
    
    if not t_id:
        available = ", ".join([t['name'] for t in t_result.get('transitions', [])])
        return f"Transition '{transition_name}' not found. Available: {available}"
    
    result = await make_jira_request("POST", f"/rest/api/3/issue/{issue_key}/transitions", {"transition": {"id": t_id}})
    
    if "error" in result:
        return f"Error transitioning: {result.get('message')}"
    return f"Transitioned {issue_key} to {transition_name}."

# === RESOURCES ===

@mcp.resource("jira://projects")
async def get_projects() -> str:
    """Get a list of all Jira projects."""
    result = await make_jira_request("GET", "/rest/api/3/project")
    
    if "error" in result:
        return f"Error retrieving projects: {result.get('message', 'Unknown error')}"
    
    projects = []
    for project in result:
        projects.append(f"{project.get('key')}: {project.get('name')}")
    
    return "\n".join(projects)

if __name__ == "__main__":
    mcp.run()