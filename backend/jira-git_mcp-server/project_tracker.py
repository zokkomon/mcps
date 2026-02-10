import asyncio
import os
import json
import time
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from dotenv import load_dotenv
from collections import defaultdict
from google.genai import types
from google import genai

from github_client import GitHubMCPClient
from jira_client import JiraMCPClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

load_dotenv()

# --- CONFIGURATION ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai_client = genai.Client(api_key=GEMINI_API_KEY)
else:
    logging.warning("GEMINI_API_KEY not found. LLM analysis will be disabled.")
    genai_client = None

JIRA_TO_GITHUB_MAP = {
    "AL": ["InfiniumDevIO/Ample-Frontend", "InfiniumDevIO/Ample-Backend"],
    "BV3": ["InfiniumDevIO/BlueValley_Conversational_AI_Demo"],
    "CB": ["InfiniumDevIO/Casagrand-Banglore"],
    "CAS": ["InfiniumDevIO/Casagrand_Backend", "InfiniumDevIO/Casasgrand", "InfiniumDevIO/casagrand-blr-backend"],
    "C3": ["InfiniumDevIO/Centroid"],
    "CEN": ["InfiniumDevIO/Century"],
    "CE": ["InfiniumDevIO/Century"],
    "CXDT2": ["InfiniumDevIO/circle-design-frontend", "InfiniumDevIO/starter-digital-tool-premium"],
    "D3": ["InfiniumDevIO/DRA"],
    "DI": ["InfiniumDevIO/DRA-Backend"],
    "GMM": ["InfiniumDevIO/Million_minds", "InfiniumDevIO/Million_Minds-Backend"],
    "GERA": ["InfiniumDevIO/Gera-Frontend", "InfiniumDevIO/Gera-Backend"],
    "G3": ["InfiniumDevIO/Gera-360-Viewer"],
    "KP": ["InfiniumDevIO/Kolte-Patil"],
    "PRIM": ["InfiniumDevIO/Primarc", "InfiniumDevIO/Primarc-Backend"],
    "RM": ["InfiniumDevIO/Rajyash"],
    "RAT": ["InfiniumDevIO/Ratna"],
    "RAT3D": ["InfiniumDevIO/Ratna"],
    "SC": ["InfiniumDevIO/Centroid"],
    "SKYI": ["InfiniumDevIO/SkyI", "InfiniumDevIO/skyi-Backend"],
}


class GeminiProgressAnalyzer:
    """Use Gemini LLM to intelligently match tickets to commits"""
    
    def __init__(self):
        self.model = "gemini-3-pro-preview"
        self.client = genai_client
    
    def analyze_assignee_progress(
        self, 
        assignee_name: str,
        tickets: List[Dict], 
        commits: List[Dict],
        project_key: str
    ) -> List[Dict]:
        """
        Use Gemini to analyze which tickets are completed based on commits
        
        Returns:
            List of ticket analysis with status, confidence, and reasoning
        """
        if not self.client:
            logging.warning("Gemini client not available, skipping LLM analysis")
            return self._fallback_analysis(tickets)
        
        # Prepare ticket context
        tickets_context = []
        for ticket in tickets:
            tickets_context.append({
                "key": ticket['key'],
                "summary": ticket['summary'],
                "status": ticket['status'],
                "type": ticket['issue_type'],
                "priority": ticket['priority']
            })
        
        # Prepare commit context
        commits_context = []
        for commit in commits:
            commits_context.append({
                "sha": commit.get('sha', '')[:7],
                "message": commit.get('message', ''),
                "author": commit.get('author_name', ''),
                "date": commit.get('date', ''),
                "repo": commit.get('repo', '')
            })
        
        prompt = f"""
            You are a Senior Technical Project Manager analyzing JIRA ticket completion based on GitHub commits.

            ### CONTEXT:
            - Project: {project_key}
            - Assignee: {assignee_name}
            - Total Tickets: {len(tickets)}
            - Total Commits: {len(commits)}

            ### JIRA TICKETS (Tasks assigned):
            {json.dumps(tickets_context, indent=2)}

            ### GITHUB COMMITS (Recent development activity):
            {json.dumps(commits_context, indent=2)}

            ### ANALYSIS INSTRUCTIONS:
            For each JIRA ticket, determine if it has been completed by analyzing the commit messages.

            **Matching Strategies:**
            1. **Explicit Reference**: Commit message contains ticket key (e.g., "AL-123" or "fix AL-123")
            2. **Semantic Match**: Commit message describes work related to ticket summary
            - Example: Ticket "Fix login button alignment" → Commit "adjusted auth page button styles"
            3. **Component Match**: Commit affects components mentioned in ticket
            4. **Author Match**: Commits by the same assignee working on related functionality

            **Status Determination:**
            - **COMPLETED** (confidence 90-100%): Strong explicit reference or multiple semantic matches
            - **LIKELY_DONE** (confidence 60-89%): Good semantic match or related work found
            - **IN_PROGRESS** (confidence 30-59%): Partial match or related commits but incomplete
            - **PENDING** (confidence 0-29%): No relevant commits found

            **Important:**
            - Be thorough - check ALL commits for each ticket
            - Consider variations in ticket key format (AL-1, AL1, al-1, etc.)
            - Look for semantic connections even without explicit references
            - Multiple weak signals can indicate completion
            - If unsure, err on the side of PENDING

            ### OUTPUT FORMAT (JSON ONLY, NO MARKDOWN):
            Return a JSON array of objects:
            [
                {{
                    "ticket_key": "AL-1",
                    "summary": "Ticket summary",
                    "status": "COMPLETED",
                    "confidence": 95,
                    "reasoning": "Found explicit reference in commit 7b3f1a: 'fix AL-1 login issue'. Additionally, commit a2c4d mentions 'login page updates' which aligns with ticket scope.",
                    "matched_commits": ["7b3f1a", "a2c4d"],
                    "match_types": ["explicit_reference", "semantic_match"]
                }}
            ]
        """
        
        try:
            time.sleep(5)
            logging.info(f"Analyzing {len(tickets)} tickets with Gemini LLM...")
            
            contents = [
                types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=prompt)],
                ),
            ]
            
            generate_content_config = types.GenerateContentConfig(
                temperature=0.1,  
                response_mime_type="application/json"
            )
            
            response = self.client.models.generate_content(
                model=self.model,
                contents=contents,
                config=generate_content_config
            )
            
            analysis_result = response.text
            results = json.loads(analysis_result)
            
            logging.info(f"✓ Gemini analyzed {len(results)} tickets")
            return results
            
        except Exception as e:
            logging.error(f"Gemini analysis failed: {e}")
            logging.warning("Falling back to basic analysis")
            return self._fallback_analysis(tickets)
    
    def _fallback_analysis(self, tickets: List[Dict]) -> List[Dict]:
        """Fallback when LLM is unavailable"""
        return [
            {
                "ticket_key": ticket['key'],
                "summary": ticket['summary'],
                "status": "PENDING",
                "confidence": 0,
                "reasoning": "LLM analysis unavailable - manual review required",
                "matched_commits": [],
                "match_types": []
            }
            for ticket in tickets
        ]


class DynamicProjectTracker:
    """
    Automatically discovers GitHub user and Jira projects
    """
    
    def __init__(self):
        self.jira_client: Optional[JiraMCPClient] = None
        self.github_client: Optional[GitHubMCPClient] = None
        self.github_user_data: Optional[Dict] = None
        self.jira_projects: List[Dict] = []
        self.llm_analyzer = GeminiProgressAnalyzer()
        
    async def connect_clients(self):
        """Initialize both clients"""
        self.jira_client = JiraMCPClient()
        self.github_client = GitHubMCPClient()
        
        await self.jira_client.connect()
        await self.github_client.connect()
        logging.info("✓ Connected to Jira and GitHub MCP Servers")
    
    async def disconnect_clients(self):
        """Disconnect both clients - with proper error handling"""
        errors = []
        
        if self.github_client:
            try:
                await self.github_client.disconnect()
            except Exception as e:
                errors.append(f"GitHub disconnect error: {e}")
        
        if self.jira_client:
            try:
                await self.jira_client.disconnect()
            except Exception as e:
                errors.append(f"Jira disconnect error: {e}")
        
        if errors:
            logging.warning("Disconnect completed with warnings: " + "; ".join(errors))
        else:
            logging.info("✓ Disconnected from all servers")
    
    async def discover_github_user(self) -> Dict[str, str]:
        """Auto-discover the authenticated GitHub user"""
        logging.info("Discovering GitHub user...")
        
        user = await self.github_client.get_current_user()
        
        if isinstance(user, dict):
            self.github_user_data = user
            
            logging.info(f"✓ Authenticated as: {user.get('login')} ({user.get('name', 'N/A')})")
            
            return {
                'login': user.get('login'),
                'name': user.get('name'),
                'email': user.get('email'),
                'url': user.get('html_url')
            }
        else:
            logging.error("Failed to get GitHub user information")
            raise Exception("Could not authenticate GitHub user")
    
    async def discover_jira_projects(self) -> List[Dict[str, str]]:
        """Auto-discover all Jira projects"""
        logging.info("Discovering Jira projects...")
        projects_str = await self.jira_client.get_all_projects()
        
        projects = []
        for line in projects_str.strip().split('\n'):
            if ':' in line:
                key, name = line.split(':', 1)
                projects.append({
                    'key': key.strip(),
                    'name': name.strip()
                })
        
        self.jira_projects = projects
        logging.info(f"✓ Found {len(projects)} Jira projects")
        
        return projects
    
    async def get_project_issues_by_assignee(
        self, 
        project_key: str,
        status_filter: str = "all"
    ) -> Dict[str, List[Dict]]:
        """Fetch all issues from a Jira project grouped by assignee"""
        if status_filter == "active":
            jql = f"project = {project_key} AND statusCategory != Done ORDER BY updated DESC"
        elif status_filter == "all":
            jql = f"project = {project_key} ORDER BY updated DESC"
        else:
            jql = f"project = {project_key} AND status = '{status_filter}' ORDER BY updated DESC"
        
        logging.info(f"Fetching issues from project {project_key}...")
        
        result = await self.jira_client.call_tool("search_issues", {
            "jql": jql,
            "max_results": 100
        })
        
        # Parse result
        try:
            if isinstance(result, str):
                if result.strip().startswith('{'):
                    issues_data = json.loads(result)
                else:
                    issues_data = self._parse_jira_string_response(result)
            else:
                issues_data = result
        except Exception as e:
            logging.error(f"Error parsing Jira response: {e}")
            return {}
        
        # Group by assignee
        assignee_issues = defaultdict(list)
        issues_list = issues_data.get('issues', []) if isinstance(issues_data, dict) else []
        
        for issue in issues_list:
            fields = issue.get('fields', {})
            assignee_info = fields.get('assignee')
            
            if assignee_info:
                assignee_key = assignee_info.get('emailAddress') or assignee_info.get('displayName', 'Unassigned')
            else:
                assignee_key = 'Unassigned'
            
            issue_summary = {
                'key': issue.get('key'),
                'summary': fields.get('summary', 'No summary'),
                'status': fields.get('status', {}).get('name', 'Unknown'),
                'assignee': assignee_info.get('displayName', 'Unassigned') if assignee_info else 'Unassigned',
                'assignee_email': assignee_info.get('emailAddress', '') if assignee_info else '',
                'issue_type': fields.get('issuetype', {}).get('name', 'Unknown'),
                'priority': fields.get('priority', {}).get('name', 'None'),
            }
            
            assignee_issues[assignee_key].append(issue_summary)
        
        logging.info(f"Found {len(assignee_issues)} assignees with issues")
        return dict(assignee_issues)
    
    def _parse_jira_string_response(self, response: str) -> Dict:
        """Parse formatted string response from Jira"""
        issues = []
        lines = response.strip().split('\n')
        
        for line in lines[1:]:  # Skip header
            if ':' in line:
                parts = line.split(':')
                if len(parts) >= 2:
                    key = parts[0].strip()
                    rest = parts[1].strip()
                    
                    summary = rest.split('[')[0].strip() if '[' in rest else rest
                    status = 'Unknown'
                    if '[' in rest and ']' in rest:
                        status = rest.split('[')[1].split(']')[0].strip()
                    
                    assignee = None
                    if '(' in rest and ')' in rest:
                        assignee_name = rest.split('(')[1].split(')')[0].strip()
                        if assignee_name != 'Unassigned':
                            assignee = {'displayName': assignee_name}
                    
                    issues.append({
                        'key': key,
                        'fields': {
                            'summary': summary,
                            'status': {'name': status},
                            'assignee': assignee,
                            'issuetype': {'name': 'Unknown'},
                            'priority': {'name': 'None'}
                        }
                    })
        
        return {'issues': issues}
    
    async def get_commits_for_repos(
        self, 
        repo_full_names: List[str],
        assignee_email: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict]:
        all_commits = []
        
        for full_name in repo_full_names:
            try:
                owner, repo = full_name.split('/')
            except ValueError:
                logging.warning(f"Invalid repo format: {full_name} (expected owner/repo)")
                continue
            
            logging.info(f"Fetching commits from {owner}/{repo}")
            
            try:
                # FIXED: Use the correct method from github_client.py
                result = await self.github_client.call_tool("list_commits", {
                    "owner": owner,
                    "repo": repo,
                    "page": 1,
                    "per_page": limit
                })
                
                # Parse the result
                commits_data = self.github_client.safe_parse(result, "list_commits")
                
                if isinstance(commits_data, list):
                    for commit in commits_data:
                        commit_data = {
                            'repo': repo,
                            'full_name': full_name,
                            'sha': commit.get('sha', '')[:7],
                            'message': commit.get('commit', {}).get('message', ''),
                            'author_name': commit.get('commit', {}).get('author', {}).get('name', ''),
                            'author_email': commit.get('commit', {}).get('author', {}).get('email', ''),
                            'date': commit.get('commit', {}).get('author', {}).get('date', ''),
                            'full_sha': commit.get('sha', '')
                        }
                        
                        if assignee_email:
                            if assignee_email.lower() in commit_data['author_email'].lower():
                                all_commits.append(commit_data)
                        else:
                            all_commits.append(commit_data)
                elif isinstance(commits_data, str) and ("404" in commits_data or "failed" in commits_data):
                    logging.warning(f"Repository not accessible: {owner}/{repo}")
                else:
                    logging.warning(f"Unexpected response for {owner}/{repo}")
                            
            except Exception as e:
                logging.warning(f"Error fetching commits from {owner}/{repo}: {e}")
                continue
        
        logging.info(f"Total commits fetched: {len(all_commits)}")
        return all_commits
    
    async def analyze_project(
        self,
        project_key: str,
        status_filter: str = "all"
    ) -> Dict[str, Any]:
        """Complete analysis with LLM-powered matching"""
        logging.info(f"=" * 70)
        logging.info(f"ANALYZING PROJECT: {project_key}")
        logging.info(f"=" * 70)
        
        # Get mapped repositories
        repos = JIRA_TO_GITHUB_MAP.get(project_key, [])
        if not repos:
            logging.warning(f"No GitHub repositories mapped for project {project_key}")
            return {"error": f"No repository mapping found for {project_key}"}
        
        logging.info(f"Mapped repositories: {', '.join(repos)}")
        
        # Fetch issues grouped by assignee
        assignee_issues = await self.get_project_issues_by_assignee(
            project_key, 
            status_filter
        )
        
        if not assignee_issues:
            logging.warning(f"No issues found for project {project_key}")
            return {"error": "No issues found"}
        
        # Analyze each assignee
        analysis_results = {}
        
        for assignee, issues in assignee_issues.items():
            logging.info(f"\n--- Analyzing: {assignee} ({len(issues)} tickets) ---")
            
            assignee_email = issues[0].get('assignee_email', '') if issues else None
            
            # Fetch commits (now using correct method)
            commits = await self.get_commits_for_repos(
                repos,
                assignee_email=assignee_email,
                limit=100
            )
            
            if not commits:
                logging.info(f"No commits found for {assignee}")
                analysis_results[assignee] = {
                    'tickets': issues,
                    'commits': [],
                    'matches': [],
                    'summary': {
                        'total_tickets': len(issues),
                        'completed': 0,
                        'likely_done': 0,
                        'in_progress': 0,
                        'pending': len(issues),
                        'total_commits': 0
                    }
                }
                continue
            
            llm_results = self.llm_analyzer.analyze_assignee_progress(
                assignee_name=assignee,
                tickets=issues,
                commits=commits,
                project_key=project_key
            )
            
            # Convert LLM results to match format
            matches = []
            for llm_result in llm_results:
                ticket = next((t for t in issues if t['key'] == llm_result['ticket_key']), None)
                if not ticket:
                    continue
                
                # Find matched commits
                matched_commit_objs = []
                for commit_sha in llm_result.get('matched_commits', []):
                    commit = next((c for c in commits if commit_sha in c['sha']), None)
                    if commit:
                        matched_commit_objs.append({
                            'commit': commit,
                            'score': llm_result['confidence'],
                            'match_type': llm_result.get('match_types', [])
                        })
                
                matches.append({
                    'ticket': ticket,
                    'status': llm_result['status'],
                    'confidence': llm_result['confidence'],
                    'reasoning': llm_result['reasoning'],
                    'matched_commits': matched_commit_objs,
                    'total_matches': len(matched_commit_objs)
                })
            
            summary = {
                'total_tickets': len(issues),
                'completed': sum(1 for m in matches if m['status'] == 'COMPLETED'),
                'likely_done': sum(1 for m in matches if m['status'] == 'LIKELY_DONE'),
                'in_progress': sum(1 for m in matches if m['status'] == 'IN_PROGRESS'),
                'pending': sum(1 for m in matches if m['status'] == 'PENDING'),
                'total_commits': len(commits)
            }
            
            analysis_results[assignee] = {
                'tickets': issues,
                'commits': commits,
                'matches': matches,
                'summary': summary
            }
            
            logging.info(f"Summary: {summary['completed']} | {summary['likely_done']} | {summary['in_progress']} | {summary['pending']}")
        
        return {
            'project_key': project_key,
            'repositories': repos,
            'assignee_analysis': analysis_results,
            'timestamp': datetime.now().isoformat()
        }
    
    def generate_report(self, analysis: Dict[str, Any]) -> str:
        """Generate formatted report with LLM insights"""
        if 'error' in analysis:
            return f"Error: {analysis['error']}"
        
        report = []
        report.append("=" * 80)
        report.append(f"PROJECT COMPLETION REPORT: {analysis['project_key']}")
        report.append(f"Generated: {analysis['timestamp']}")
        report.append(f"Repositories: {', '.join(analysis['repositories'])}")
        report.append("=" * 80)
        
        for assignee, data in analysis['assignee_analysis'].items():
            report.append(f"\n ASSIGNEE: {assignee}")
            report.append("-" * 80)
            
            summary = data['summary']
            report.append(f"Total Tickets: {summary['total_tickets']}")
            report.append(f"Total Commits: {summary['total_commits']}")
            report.append(f" Completed: {summary['completed']}")
            report.append(f" Likely Done: {summary['likely_done']}")
            report.append(f" In Progress: {summary['in_progress']}")
            report.append(f" Pending: {summary['pending']}")
            
            report.append(f"\nTICKET DETAILS:")
            for match in data['matches']:
                ticket = match['ticket']
                status_emoji = {
                    'COMPLETED': '',
                    'LIKELY_DONE': '',
                    'IN_PROGRESS': '',
                    'PENDING': ''
                }.get(match['status'], '')
                
                report.append(f"\n  {status_emoji} [{ticket['key']}] {ticket['summary']}")
                report.append(f"     Jira Status: {ticket['status']} | Type: {ticket['issue_type']}")
                report.append(f"     Analysis: {match['status']} (Confidence: {match['confidence']}%)")
                report.append(f"     Reasoning: {match.get('reasoning', 'N/A')}")
                
                if match['matched_commits']:
                    report.append(f"     Related Commits:")
                    for mc in match['matched_commits'][:3]:
                        commit = mc['commit']
                        msg = commit['message'].split('\n')[0][:70]
                        report.append(f"       - [{commit['repo']}] {commit['sha']}: {msg}")
        
        report.append("\n" + "=" * 80)
        return "\n".join(report)


async def interactive_mode():
    """Interactive mode with LLM-powered analysis"""
    tracker = DynamicProjectTracker()
    
    try:
        await tracker.connect_clients()
        print("\n" + "=" * 70)
        print("STEP 1: GITHUB USER DISCOVERY")
        print("=" * 70)
        github_user = await tracker.discover_github_user()
        
        # 2. Auto-discover Jira projects
        print("\n" + "=" * 70)
        print("STEP 2: JIRA PROJECTS DISCOVERY")
        print("=" * 70)
        projects = await tracker.discover_jira_projects()
        
        # Display projects
        print("\nAvailable Jira Projects:")
        for i, proj in enumerate(projects, 1):
            mapped_repos = JIRA_TO_GITHUB_MAP.get(proj['key'], [])
            status = "✓" if mapped_repos else "(no repo mapping)"
            print(f"  {i}. [{proj['key']}] {proj['name']} {status}")
        
        # 3. Let user select project
        print("\n" + "=" * 70)
        print("STEP 3: PROJECT SELECTION")
        print("=" * 70)
        
        while True:
            try:
                choice = input("\nEnter project number to analyze (or 'all' for all projects, 'q' to quit): ").strip()
                
                if choice.lower() == 'q':
                    print("Exiting...")
                    return
                
                if choice.lower() == 'all':
                    for proj in projects:
                        if JIRA_TO_GITHUB_MAP.get(proj['key']):
                            try:
                                analysis = await tracker.analyze_project(
                                    project_key=proj['key'],
                                    status_filter="all"
                                )
                                
                                report = tracker.generate_report(analysis)
                                print(f"\n{report}")
                                
                                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                                filename = f"report_{proj['key']}_{timestamp}.txt"
                                with open(filename, 'w') as f:
                                    f.write(report)
                                print(f"✓ Report saved to {filename}")
                            except Exception as e:
                                logging.error(f"Error analyzing {proj['key']}: {e}")
                                continue
                    break
                
                # Single project
                project_index = int(choice) - 1
                if 0 <= project_index < len(projects):
                    selected_project = projects[project_index]
                    
                    # Analyze
                    analysis = await tracker.analyze_project(
                        project_key=selected_project['key'],
                        status_filter="all"
                    )
                    
                    # Generate and display report
                    report = tracker.generate_report(analysis)
                    print(f"\n{report}")
                    
                    # Save report
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    filename = f"report_{selected_project['key']}_{timestamp}.txt"
                    with open(filename, 'w') as f:
                        f.write(report)
                    print(f"\n✓ Report saved to {filename}")
                    
                    # Ask if user wants to analyze another
                    another = input("\nAnalyze another project? (y/n): ").strip().lower()
                    if another != 'y':
                        break
                else:
                    print("Invalid project number. Try again.")
                    
            except ValueError:
                print("Invalid input. Please enter a number or 'all' or 'q'.")
            except Exception as e:
                logging.error(f"Error: {e}")
                import traceback
                traceback.print_exc()
                break
        
    except Exception as e:
        logging.error(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await tracker.disconnect_clients()


async def main():
    """Run in interactive mode"""
    await interactive_mode()


if __name__ == "__main__":
    asyncio.run(main())