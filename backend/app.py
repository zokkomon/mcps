import asyncio
import os
import sys
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from flask import Flask, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv

sys.path.append(os.path.join(os.getcwd(), 'hubspot-mcp-server'))
sys.path.append(os.path.join(os.getcwd(), 'jira-git_mcp-server'))

from hubspot_client import HubSpotMCPClient
from project_tracker import DynamicProjectTracker

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

app = Flask(__name__)
CORS(app)

hubspot_client = None
project_tracker = None


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'services': {
            'hubspot': hubspot_client is not None,
            'jira_github': project_tracker is not None
        }
    })


# ==================== HUBSPOT ENDPOINTS ====================

@app.route('/api/hubspot/contacts/recent', methods=['GET'])
def get_recent_contacts():
    """Get contacts from last 30 days with structured data"""
    try:
        days = int(request.args.get('days', 30))
        limit = int(request.args.get('limit', 200))
        
        today = datetime.now()
        start_date = today - timedelta(days=days)
        
        async def fetch_contacts():
            async with HubSpotMCPClient() as client:
                result = await client.list_contacts_by_date_range(
                    start_date=start_date.strftime('%Y-%m-%d'),
                    end_date=today.strftime('%Y-%m-%d'),
                    limit=limit
                )
                return result
        
        contacts_data = asyncio.run(fetch_contacts())
        
        return jsonify({
            'success': True,
            'data': contacts_data,
            'period': {
                'start_date': start_date.strftime('%Y-%m-%d'),
                'end_date': today.strftime('%Y-%m-%d'),
                'days': days
            },
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logging.error(f"Error fetching recent contacts: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/hubspot/activities/recent', methods=['GET'])
def get_recent_activities():
    """Get activities for contacts from last 30 days with structured data"""
    try:
        days = int(request.args.get('days', 30))
        limit = int(request.args.get('limit', 100))
        
        today = datetime.now()
        start_date = today - timedelta(days=days)
        
        async def fetch_activities():
            async with HubSpotMCPClient() as client:
                result = await client.get_recent_activities_by_date(
                    start_date=start_date.strftime('%Y-%m-%d'),
                    end_date=today.strftime('%Y-%m-%d'),
                    limit_contacts=limit
                )
                return result
        
        activities_data = asyncio.run(fetch_activities())
        
        return jsonify({
            'success': True,
            'data': activities_data,
            'period': {
                'start_date': start_date.strftime('%Y-%m-%d'),
                'end_date': today.strftime('%Y-%m-%d'),
                'days': days
            },
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logging.error(f"Error fetching recent activities: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'data': {
                'error': str(e),
                'activities': []
            }
        }), 500


@app.route('/api/hubspot/contacts/date-range', methods=['GET'])
def get_contacts_by_date_range():
    """Get contacts for custom date range"""
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        limit = int(request.args.get('limit', 200))
        
        if not start_date or not end_date:
            return jsonify({
                'success': False,
                'error': 'start_date and end_date are required'
            }), 400
        
        async def fetch_contacts():
            async with HubSpotMCPClient() as client:
                result = await client.list_contacts_by_date_range(
                    start_date=start_date,
                    end_date=end_date,
                    limit=limit
                )
                return result
        
        contacts_data = asyncio.run(fetch_contacts())
        
        return jsonify({
            'success': True,
            'data': contacts_data,
            'period': {
                'start_date': start_date,
                'end_date': end_date
            },
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logging.error(f"Error fetching contacts by date range: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ==================== JIRA/GITHUB ENDPOINTS ====================

@app.route('/api/projects/list', methods=['GET'])
def list_projects():
    """Get all available Jira projects"""
    try:
        async def fetch_projects():
            tracker = DynamicProjectTracker()
            await tracker.connect_clients()
            try:
                projects = await tracker.discover_jira_projects()
                return projects
            finally:
                await tracker.disconnect_clients()
        
        projects = asyncio.run(fetch_projects())
        
        return jsonify({
            'success': True,
            'data': projects,
            'count': len(projects),
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logging.error(f"Error listing projects: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/projects/<project_key>/analyze', methods=['GET'])
def analyze_project(project_key):
    """Analyze a specific project with LLM-powered insights"""
    try:
        status_filter = request.args.get('status_filter', 'active')
        
        async def perform_analysis():
            tracker = DynamicProjectTracker()
            await tracker.connect_clients()
            try:
                analysis = await tracker.analyze_project(
                    project_key=project_key,
                    status_filter=status_filter
                )
                return analysis
            finally:
                await tracker.disconnect_clients()
        
        analysis_result = asyncio.run(perform_analysis())
        
        if 'error' in analysis_result:
            return jsonify({
                'success': False,
                'error': analysis_result['error']
            }), 404
        
        return jsonify({
            'success': True,
            'data': analysis_result,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logging.error(f"Error analyzing project {project_key}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/projects/analyze-all', methods=['GET'])
def analyze_all_projects():
    """Analyze all projects with repository mappings"""
    try:
        status_filter = request.args.get('status_filter', 'active')
        
        async def perform_batch_analysis():
            tracker = DynamicProjectTracker()
            await tracker.connect_clients()
            
            try:
                projects = await tracker.discover_jira_projects()
                results = []
                
                # Import mapping
                from project_tracker import JIRA_TO_GITHUB_MAP
                
                for project in projects:
                    if JIRA_TO_GITHUB_MAP.get(project['key']):
                        try:
                            analysis = await tracker.analyze_project(
                                project_key=project['key'],
                                status_filter=status_filter
                            )
                            results.append(analysis)
                        except Exception as e:
                            logging.error(f"Error analyzing {project['key']}: {e}")
                            results.append({
                                'project_key': project['key'],
                                'error': str(e)
                            })
                
                return results
            finally:
                await tracker.disconnect_clients()
        
        all_results = asyncio.run(perform_batch_analysis())
        
        return jsonify({
            'success': True,
            'data': all_results,
            'count': len(all_results),
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logging.error(f"Error in batch analysis: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/projects/<project_key>/assignees', methods=['GET'])
def get_project_assignees(project_key):
    """Get all assignees and their ticket counts for a project"""
    try:
        async def fetch_assignees():
            tracker = DynamicProjectTracker()
            await tracker.connect_clients()
            try:
                assignee_issues = await tracker.get_project_issues_by_assignee(
                    project_key=project_key,
                    status_filter='active'
                )
                
                assignee_summary = []
                for assignee, issues in assignee_issues.items():
                    assignee_summary.append({
                        'assignee': assignee,
                        'email': issues[0].get('assignee_email', '') if issues else '',
                        'ticket_count': len(issues),
                        'tickets': issues
                    })
                
                return assignee_summary
            finally:
                await tracker.disconnect_clients()
        
        assignees = asyncio.run(fetch_assignees())
        
        return jsonify({
            'success': True,
            'data': assignees,
            'project_key': project_key,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logging.error(f"Error fetching assignees for {project_key}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


if __name__ == '__main__':
    print("=" * 70)
    print("STARTING PROJECT TRACKER API SERVER")
    print("=" * 70)
    print("\nAvailable Endpoints:")
    print("  - GET  /health")
    print("  - GET  /api/hubspot/contacts/recent?days=30&limit=200")
    print("  - GET  /api/hubspot/activities/recent?days=30&limit=100")
    print("  - GET  /api/hubspot/contacts/date-range?start_date=2025-01-01&end_date=2025-01-31")
    print("  - GET  /api/projects/list")
    print("  - GET  /api/projects/<project_key>/analyze?status_filter=active")
    print("  - GET  /api/projects/<project_key>/assignees")
    print("  - GET  /api/projects/analyze-all?status_filter=active")
    print("\n" + "=" * 70)
    
    app.run(debug=True, host='0.0.0.0', port=5000)