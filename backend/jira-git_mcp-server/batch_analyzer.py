# batch_analyzer.py
import asyncio
from project_tracker import ProjectAssigneeTracker
from config import GITHUB_OWNER, JIRA_TO_GITHUB_MAP
from datetime import datetime
import json

async def analyze_all_projects():
    """Analyze all mapped projects"""
    
    tracker = ProjectAssigneeTracker(GITHUB_OWNER)
    await tracker.connect_clients()
    
    all_results = {}
    
    try:
        for project_key in JIRA_TO_GITHUB_MAP.keys():
            print(f"\n{'='*70}")
            print(f"Analyzing Project: {project_key}")
            print(f"{'='*70}")
            
            try:
                analysis = await tracker.analyze_project(
                    project_key=project_key,
                    status_filter="active"
                )
                all_results[project_key] = analysis
                
                # Print quick summary
                if 'assignee_analysis' in analysis:
                    total_completed = sum(
                        data['summary']['completed'] + data['summary']['likely_done']
                        for data in analysis['assignee_analysis'].values()
                    )
                    total_tickets = sum(
                        data['summary']['total_tickets']
                        for data in analysis['assignee_analysis'].values()
                    )
                    print(f"✅ Summary: {total_completed}/{total_tickets} tickets completed/likely done")
                
            except Exception as e:
                print(f"❌ Error analyzing {project_key}: {e}")
                all_results[project_key] = {"error": str(e)}
            
            # Small delay to avoid rate limiting
            await asyncio.sleep(2)
        
        # Save combined results
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"batch_analysis_{timestamp}.json"
        
        with open(filename, 'w') as f:
            json.dump(all_results, f, indent=2, default=str)
        
        print(f"\n✅ Batch analysis complete. Results saved to {filename}")
        
    finally:
        await tracker.disconnect_clients()

if __name__ == "__main__":
    asyncio.run(analyze_all_projects())