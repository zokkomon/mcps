from fastapi import FastAPI
import asyncio
import json
import logging
from typing import Any, Dict

# Import your MCP clients
from jira_client import JiraMCPClient
from github_client import GitHubMCPClient
from hubspot_client import HubSpotMCPClient
from analyzer import ProgressAnalyzer

app = FastAPI()

JIRA_PROJECT_KEY = "YOUR_JIRA_PROJECT"
TARGET_REPO_OWNER = "owner"
TARGET_REPO_NAME = "repo"

@app.get("/jira-github/progress")
async def analyze_jira_github_progress() -> Any:
    analyzer = ProgressAnalyzer()

    async with JiraMCPClient() as jira, GitHubMCPClient() as gh:
        jql = f"project = {JIRA_PROJECT_KEY} AND statusCategory != Done ORDER BY updated DESC"
        jira_data_raw = await jira.search_issues(jql=jql, limit=10)

        try:
            jira_issues = json.loads(jira_data_raw)
        except Exception:
            jira_issues = jira_data_raw

        commits = await gh.list_commits(TARGET_REPO_OWNER, TARGET_REPO_NAME)
        if not commits:
            return {"error": "No GitHub commits found"}

        analysis_json = analyzer.analyze_progress(jira_issues, commits)

        try:
            return json.loads(analysis_json)
        except json.JSONDecodeError:
            return {"raw_response": analysis_json}

@app.get("/hubspot/contacts")
async def hubspot_contacts():
    async with HubSpotMCPClient() as client:
        return {"contacts": await client.list_contacts(limit=10)}

@app.get("/hubspot/contact/{email}")
async def hubspot_contact_status(email: str):
    async with HubSpotMCPClient() as client:
        status = await client.get_contact_status(email)
        activities = await client.get_activities(email, limit=5)
        return {"email": email, "status": status, "activities": activities}

@app.get("/hubspot/recent")
async def hubspot_recent():
    async with HubSpotMCPClient() as client:
        return {"recent": await client.get_recent_contacts_resource()}
