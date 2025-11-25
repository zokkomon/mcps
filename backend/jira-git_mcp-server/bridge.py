import asyncio
import os
import json
import logging
from google.genai import types
from google import genai
from dotenv import load_dotenv
from datetime import datetime

from github_client import GitHubMCPClient
from jira_client import JiraMCPClient

# --- LOGGING CONFIGURATION ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

load_dotenv()

# --- CONFIGURATION ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TARGET_REPO_OWNER = ""
TARGET_REPO_NAME = ""
JIRA_PROJECT_KEY = ""

if GEMINI_API_KEY:
    genai_client = genai.Client(api_key=GEMINI_API_KEY)
else:
    logger.error("GEMINI_API_KEY not found. Please set it in your .env file.")
    genai_client = None

class ProgressAnalyzer:
    def __init__(self):
        self.model = "gemini-3-pro-preview"

    def analyze_progress(self, tickets, commits):
        tickets_context = []
        if isinstance(tickets, str):
            try:
                tickets_data = json.loads(tickets)
                tickets_context = tickets_data.get('issues', [])
            except Exception:
                tickets_context = str(tickets)
        elif isinstance(tickets, dict):
            tickets_context = tickets.get('issues', [])
        else:
            tickets_context = tickets

        commits_context = []
        if isinstance(commits, list):
            for c in commits:
                commits_context.append({
                    "sha": c.get('sha', '')[:7],
                    "message": c.get('commit', {}).get('message', ''),
                    "author": c.get('commit', {}).get('author', {}).get('name', ''),
                    "date": c.get('commit', {}).get('author', {}).get('date', '')
                })

        prompt = f"""
            You are a Senior Technical Project Manager. Your goal is to analyze if JIRA tasks are completed based on GITHUB commits.

            ### JIRA TICKETS (Tasks to be done):
            {json.dumps(tickets_context, indent=2)}

            ### GITHUB COMMITS (Recent activity):
            {json.dumps(commits_context, indent=2)}

            ### INSTRUCTIONS:
            1. For each Jira ticket, analyze the Git commit messages.
            2. Look for **Explicit Links** (e.g., "KAN-123" in commit message).
            3. Look for **Implicit Semantic Links** (e.g., Ticket says "Fix Login", Commit says "Patched auth bug").
            4. Determine the status: 
            - "COMPLETED" (Strong evidence in commits)
            - "LIKELY_DONE" (Semantic match found)
            - "PENDING" (No relevant commits found)
            
            ### OUTPUT FORMAT (JSON ONLY):
            Return a list of objects:
            [
                {{
                    "ticket_key": "KAN-1",
                    "summary": "Ticket Summary",
                    "status": "COMPLETED/PENDING",
                    "confidence_score": 0-100,
                    "reasoning": "Found commit '7b3f1a' which explicitly references KAN-1.",
                    "relevant_commit_sha": "7b3f1a"
                }}
            ]
        """

        logging.info("Asking Gemini to analyze linkage...")
        contents = [
            types.Content(
                role="user",
                parts=[
                    types.Part.from_text(text=prompt),
                ],
            ),
        ]

        generate_content_config = types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(
                thinking_level="LOW" 
            ),
            response_mime_type="application/json" 
        )

        response = genai_client.models.generate_content(
            model=self.model,
            contents=contents,
            config=generate_content_config
        )
        analysis_result = response.text
        return analysis_result


async def main():
    analyzer = ProgressAnalyzer()
    async with JiraMCPClient() as jira, GitHubMCPClient() as gh:
        
        logging.info(f"Fetching 'In Progress' tickets from Jira Project: {JIRA_PROJECT_KEY}...")
        jql = f"project = {JIRA_PROJECT_KEY} AND statusCategory != Done ORDER BY updated DESC"
        jira_data_raw = await jira.search_issues(jql=jql, limit=10)
        
        try:
            jira_issues = json.loads(jira_data_raw)
            count = len(jira_issues.get('issues', []))
            logging.info(f"Found {count} active issues.")
        except Exception:
            logging.warning("Could not parse Jira JSON strictly, passing raw text to LLM.")
            jira_issues = jira_data_raw

        logging.info(f"Fetching recent commits from {TARGET_REPO_OWNER}/{TARGET_REPO_NAME}...")
        commits = await gh.list_commits(TARGET_REPO_OWNER, TARGET_REPO_NAME)
        if commits:
            logging.info(f"Found {len(commits)} recent commits.")
        else:
            logging.warning("No commits found or error fetching.")
            return

        logging.info("Running LLM Analysis ")
        analysis_json = analyzer.analyze_progress(jira_issues, commits)
        
        try:
            results = json.loads(analysis_json)
            logging.info("ANALYSIS REPORT:")
            for item in results:
                status_icon = "Done" if item['status'] in ["COMPLETED", "LIKELY_DONE"] else "Pending"
                logging.info(f"{status_icon} [{item['ticket_key']}] {item['summary']}")
                logging.info(f"   Status: {item['status']} (Confidence: {item['confidence_score']}%)")
                logging.info(f"   Reason: {item['reasoning']}")
                if item.get('relevant_commit_sha'):
                    logging.info(f"   Commit: {item['relevant_commit_sha']}")
                logging.info("-" * 60)

        except json.JSONDecodeError:
            logging.error("Error decoding LLM response:")
            logging.error(analysis_json)


if __name__ == "__main__":
    asyncio.run(main())
