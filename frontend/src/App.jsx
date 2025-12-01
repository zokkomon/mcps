import React, { useState, useEffect } from 'react';
import { Activity, Users, GitBranch, CheckCircle, AlertCircle, Clock, TrendingUp, Search, Filter, Calendar, Mail, Building, ChevronDown, ChevronUp, TrendingUp as TrendIcon } from 'lucide-react';

const API_BASE_URL = 'http://localhost:5000/api';

export default function Dashboard() {
  const [activeTab, setActiveTab] = useState('projects');
  const [projects, setProjects] = useState([]);
  const [selectedProject, setSelectedProject] = useState(null);
  const [projectAnalysis, setProjectAnalysis] = useState(null);
  const [hubspotContacts, setHubspotContacts] = useState(null);
  const [hubspotActivities, setHubspotActivities] = useState(null);
  const [loading, setLoading] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [showContactDetails, setShowContactDetails] = useState(false);
  const [showActivitiesDetails, setShowActivitiesDetails] = useState(false);

  // Fetch projects on mount
  useEffect(() => {
    fetchProjects();
  }, []);

  const fetchProjects = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/projects/list`);
      const data = await response.json();
      if (data.success) {
        setProjects(data.data);
      }
    } catch (error) {
      console.error('Error fetching projects:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchProjectAnalysis = async (projectKey) => {
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/projects/${projectKey}/analyze?status_filter=active`);
      const data = await response.json();
      if (data.success) {
        setProjectAnalysis(data.data);
        setSelectedProject(projectKey);
      }
    } catch (error) {
      console.error('Error fetching project analysis:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchHubSpotData = async () => {
    setLoading(true);
    try {
      const [contactsRes, activitiesRes] = await Promise.all([
        fetch(`${API_BASE_URL}/hubspot/contacts/recent?days=30&limit=200`),
        fetch(`${API_BASE_URL}/hubspot/activities/recent?days=30&limit=100`)
      ]);
      
      const contactsData = await contactsRes.json();
      const activitiesData = await activitiesRes.json();
      
      if (contactsData.success) setHubspotContacts(contactsData);
      if (activitiesData.success) setHubspotActivities(activitiesData);
    } catch (error) {
      console.error('Error fetching HubSpot data:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (activeTab === 'hubspot') {
      fetchHubSpotData();
    }
  }, [activeTab]);

  const getStatusColor = (status) => {
    const colors = {
      'COMPLETED': 'bg-green-100 text-green-800',
      'LIKELY_DONE': 'bg-blue-100 text-blue-800',
      'IN_PROGRESS': 'bg-yellow-100 text-yellow-800',
      'PENDING': 'bg-gray-100 text-gray-800'
    };
    return colors[status] || 'bg-gray-100 text-gray-800';
  };

  const getStatusIcon = (status) => {
    const icons = {
      'COMPLETED': <CheckCircle className="w-4 h-4" />,
      'LIKELY_DONE': <TrendingUp className="w-4 h-4" />,
      'IN_PROGRESS': <Clock className="w-4 h-4" />,
      'PENDING': <AlertCircle className="w-4 h-4" />
    };
    return icons[status] || <AlertCircle className="w-4 h-4" />;
  };

  const filterTickets = (matches) => {
    if (!matches) return [];
    
    let filtered = matches;
    
    if (searchTerm) {
      filtered = filtered.filter(m => 
        m.ticket.key.toLowerCase().includes(searchTerm.toLowerCase()) ||
        m.ticket.summary.toLowerCase().includes(searchTerm.toLowerCase())
      );
    }
    
    if (statusFilter !== 'all') {
      filtered = filtered.filter(m => m.status === statusFilter);
    }
    
    return filtered;
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <h1 className="text-2xl font-bold text-gray-900">Project Tracker Dashboard</h1>
          <p className="text-sm text-gray-500 mt-1">HubSpot Integration & Jira/GitHub Analytics</p>
        </div>
      </header>

      {/* Tabs */}
      <div className="bg-white border-b">
        <div className="max-w-7xl mx-auto px-4">
          <nav className="flex space-x-8">
            <button
              onClick={() => setActiveTab('projects')}
              className={`py-4 px-1 border-b-2 font-medium text-sm ${
                activeTab === 'projects'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              <GitBranch className="w-4 h-4 inline mr-2" />
              Projects
            </button>
            <button
              onClick={() => setActiveTab('hubspot')}
              className={`py-4 px-1 border-b-2 font-medium text-sm ${
                activeTab === 'hubspot'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              <Users className="w-4 h-4 inline mr-2" />
              HubSpot
            </button>
          </nav>
        </div>
      </div>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 py-6">
        {loading && (
          <div className="flex items-center justify-center py-12">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
          </div>
        )}

        {/* Projects Tab */}
        {activeTab === 'projects' && !loading && (
          <div className="space-y-6">
            {/* Project List */}
            {!selectedProject && (
              <div className="bg-white rounded-lg shadow">
                <div className="px-6 py-4 border-b">
                  <h2 className="text-lg font-semibold text-gray-900">All Projects</h2>
                  <p className="text-sm text-gray-500 mt-1">Select a project to view detailed analysis</p>
                </div>
                <div className="p-6">
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {projects.map((project) => (
                      <button
                        key={project.key}
                        onClick={() => fetchProjectAnalysis(project.key)}
                        className="p-4 border rounded-lg hover:border-blue-500 hover:shadow-md transition text-left"
                      >
                        <div className="flex items-start justify-between">
                          <div>
                            <h3 className="font-semibold text-gray-900">{project.key}</h3>
                            <p className="text-sm text-gray-600 mt-1">{project.name}</p>
                          </div>
                          <GitBranch className="w-5 h-5 text-gray-400" />
                        </div>
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* Project Analysis */}
            {selectedProject && projectAnalysis && (
              <div className="space-y-6">
                <button
                  onClick={() => {
                    setSelectedProject(null);
                    setProjectAnalysis(null);
                  }}
                  className="text-blue-600 hover:text-blue-800 text-sm font-medium"
                >
                  ← Back to Projects
                </button>

                {/* Project Header */}
                <div className="bg-white rounded-lg shadow p-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <h2 className="text-2xl font-bold text-gray-900">{projectAnalysis.project_key}</h2>
                      <p className="text-sm text-gray-500 mt-1">
                        Repositories: {projectAnalysis.repositories.join(', ')}
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="text-sm text-gray-500">Last Updated</p>
                      <p className="text-sm font-medium">
                        {new Date(projectAnalysis.timestamp).toLocaleString()}
                      </p>
                    </div>
                  </div>
                </div>

                {/* Assignee Analysis */}
                {Object.entries(projectAnalysis.assignee_analysis).map(([assignee, data]) => (
                  <div key={assignee} className="bg-white rounded-lg shadow">
                    <div className="px-6 py-4 border-b bg-gray-50">
                      <div className="flex items-center justify-between">
                        <div>
                          <h3 className="text-lg font-semibold text-gray-900">{assignee}</h3>
                          <p className="text-sm text-gray-500 mt-1">
                            {data.summary.total_tickets} tickets • {data.summary.total_commits} commits
                          </p>
                        </div>
                        <div className="flex gap-4">
                          <div className="text-center">
                            <div className="text-2xl font-bold text-green-600">{data.summary.completed}</div>
                            <div className="text-xs text-gray-500">Completed</div>
                          </div>
                          <div className="text-center">
                            <div className="text-2xl font-bold text-blue-600">{data.summary.likely_done}</div>
                            <div className="text-xs text-gray-500">Likely Done</div>
                          </div>
                          <div className="text-center">
                            <div className="text-2xl font-bold text-yellow-600">{data.summary.in_progress}</div>
                            <div className="text-xs text-gray-500">In Progress</div>
                          </div>
                          <div className="text-center">
                            <div className="text-2xl font-bold text-gray-600">{data.summary.pending}</div>
                            <div className="text-xs text-gray-500">Pending</div>
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* Filters */}
                    <div className="px-6 py-4 border-b bg-gray-50 flex gap-4">
                      <div className="flex-1">
                        <div className="relative">
                          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
                          <input
                            type="text"
                            placeholder="Search tickets..."
                            value={searchTerm}
                            onChange={(e) => setSearchTerm(e.target.value)}
                            className="pl-10 pr-4 py-2 w-full border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                          />
                        </div>
                      </div>
                      <div className="w-48">
                        <select
                          value={statusFilter}
                          onChange={(e) => setStatusFilter(e.target.value)}
                          className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                        >
                          <option value="all">All Status</option>
                          <option value="COMPLETED">Completed</option>
                          <option value="LIKELY_DONE">Likely Done</option>
                          <option value="IN_PROGRESS">In Progress</option>
                          <option value="PENDING">Pending</option>
                        </select>
                      </div>
                    </div>

                    {/* Tickets */}
                    <div className="p-6 space-y-4">
                      {filterTickets(data.matches).map((match) => (
                        <div key={match.ticket.key} className="border rounded-lg p-4 hover:shadow-md transition">
                          <div className="flex items-start justify-between mb-3">
                            <div className="flex-1">
                              <div className="flex items-center gap-2 mb-2">
                                <span className="font-mono text-sm font-semibold text-blue-600">
                                  {match.ticket.key}
                                </span>
                                <span className={`px-2 py-1 rounded-full text-xs font-medium flex items-center gap-1 ${getStatusColor(match.status)}`}>
                                  {getStatusIcon(match.status)}
                                  {match.status.replace('_', ' ')}
                                </span>
                                <span className="px-2 py-1 bg-gray-100 text-gray-700 rounded-full text-xs">
                                  {match.confidence}% confidence
                                </span>
                              </div>
                              <h4 className="font-medium text-gray-900">{match.ticket.summary}</h4>
                              <div className="flex gap-4 mt-2 text-xs text-gray-500">
                                <span>Jira: {match.ticket.status}</span>
                                <span>Type: {match.ticket.issue_type}</span>
                                <span>Priority: {match.ticket.priority}</span>
                              </div>
                            </div>
                          </div>

                          {match.reasoning && (
                            <div className="mb-3 p-3 bg-blue-50 rounded border-l-4 border-blue-500">
                              <p className="text-sm text-gray-700">
                                <span className="font-medium">Analysis: </span>
                                {match.reasoning}
                              </p>
                            </div>
                          )}

                          {match.matched_commits && match.matched_commits.length > 0 && (
                            <div className="mt-3 space-y-2">
                              <p className="text-sm font-medium text-gray-700">Related Commits:</p>
                              {match.matched_commits.slice(0, 3).map((mc, idx) => (
                                <div key={idx} className="flex items-start gap-3 text-sm bg-gray-50 p-2 rounded">
                                  <code className="text-xs bg-gray-200 px-2 py-1 rounded font-mono">
                                    {mc.commit.sha}
                                  </code>
                                  <div className="flex-1">
                                    <p className="text-gray-900">{mc.commit.message.split('\n')[0]}</p>
                                    <p className="text-xs text-gray-500 mt-1">
                                      {mc.commit.repo} • {mc.commit.author_name}
                                    </p>
                                  </div>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* HubSpot Tab - NEW UPGRADED UI */}
        {activeTab === 'hubspot' && !loading && (
          <div className="space-y-6">
            {/* Leads by Date - Primary Section */}
            {hubspotContacts && hubspotContacts.data && (
              <div className="bg-white rounded-lg shadow">
                <div className="px-6 py-4 border-b bg-gradient-to-r from-blue-50 to-indigo-50">
                  <div className="flex items-center justify-between">
                    <div>
                      <h2 className="text-xl font-bold text-gray-900 flex items-center gap-2">
                        <TrendIcon className="w-6 h-6 text-blue-600" />
                        Leads Added by Date
                      </h2>
                      <p className="text-sm text-gray-600 mt-1">
                        {hubspotContacts.period.start_date} to {hubspotContacts.period.end_date}
                      </p>
                    </div>
                    <div className="text-right">
                      <div className="text-3xl font-bold text-blue-600">
                        {hubspotContacts.data.total_contacts}
                      </div>
                      <div className="text-sm text-gray-500">Total Contacts</div>
                    </div>
                  </div>
                </div>

                <div className="p-6">
                  {hubspotContacts.data.leads_by_date && hubspotContacts.data.leads_by_date.length > 0 ? (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                      {hubspotContacts.data.leads_by_date.map(([date, count]) => (
                        <div
                          key={date}
                          className="bg-gradient-to-br from-blue-50 to-indigo-50 rounded-lg p-4 border border-blue-200 hover:shadow-md transition"
                        >
                          <div className="flex items-center justify-between">
                            <div>
                              <div className="flex items-center gap-2 mb-1">
                                <Calendar className="w-4 h-4 text-blue-600" />
                                <span className="text-sm font-medium text-gray-600">
                                  {new Date(date).toLocaleDateString('en-US', { 
                                    month: 'short', 
                                    day: 'numeric',
                                    year: 'numeric'
                                  })}
                                </span>
                              </div>
                              <div className="text-2xl font-bold text-gray-900">{count}</div>
                              <div className="text-xs text-gray-500">
                                {count === 1 ? 'lead' : 'leads'} added
                              </div>
                            </div>
                            <div className="w-12 h-12 bg-blue-100 rounded-full flex items-center justify-center">
                              <Users className="w-6 h-6 text-blue-600" />
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-center py-8 text-gray-500">
                      No leads data available
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Contact Details - Collapsible Section */}
            {hubspotContacts && hubspotContacts.data && hubspotContacts.data.contacts && (
              <div className="bg-white rounded-lg shadow">
                <button
                  onClick={() => setShowContactDetails(!showContactDetails)}
                  className="w-full px-6 py-4 border-b flex items-center justify-between hover:bg-gray-50 transition"
                >
                  <div className="flex items-center gap-3">
                    <Users className="w-5 h-5 text-gray-600" />
                    <div className="text-left">
                      <h3 className="text-lg font-semibold text-gray-900">
                        All Contacts ({hubspotContacts.data.contacts.length})
                      </h3>
                      <p className="text-sm text-gray-500">
                        Detailed contact information
                      </p>
                    </div>
                  </div>
                  {showContactDetails ? (
                    <ChevronUp className="w-5 h-5 text-gray-400" />
                  ) : (
                    <ChevronDown className="w-5 h-5 text-gray-400" />
                  )}
                </button>

                {showContactDetails && (
                  <div className="p-6">
                    <div className="overflow-x-auto">
                      <table className="min-w-full divide-y divide-gray-200">
                        <thead className="bg-gray-50">
                          <tr>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                              Contact
                            </th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                              Email
                            </th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                              Status
                            </th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                              Company
                            </th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                              Created
                            </th>
                          </tr>
                        </thead>
                        <tbody className="bg-white divide-y divide-gray-200">
                          {hubspotContacts.data.contacts.map((contact, index) => (
                            <tr key={index} className="hover:bg-gray-50">
                              <td className="px-6 py-4 whitespace-nowrap">
                                <div className="flex items-center">
                                  <div className="w-10 h-10 bg-blue-100 rounded-full flex items-center justify-center">
                                    <span className="text-blue-600 font-semibold">
                                      {contact.name.charAt(0)}
                                    </span>
                                  </div>
                                  <div className="ml-4">
                                    <div className="text-sm font-medium text-gray-900">
                                      {contact.name}
                                    </div>
                                    <div className="text-sm text-gray-500">
                                      {contact.lifecycle_stage}
                                    </div>
                                  </div>
                                </div>
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap">
                                <div className="flex items-center text-sm text-gray-900">
                                  <Mail className="w-4 h-4 mr-2 text-gray-400" />
                                  {contact.email}
                                </div>
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap">
                                <span className="px-3 py-1 inline-flex text-xs leading-5 font-semibold rounded-full bg-green-100 text-green-800">
                                  {contact.lead_status}
                                </span>
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap">
                                <div className="flex items-center text-sm text-gray-900">
                                  <Building className="w-4 h-4 mr-2 text-gray-400" />
                                  {contact.company || 'N/A'}
                                </div>
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                                {contact.created_date}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Activities - Collapsible Section */}
            {hubspotActivities && hubspotActivities.data && (
              <div className="bg-white rounded-lg shadow">
                <button
                  onClick={() => setShowActivitiesDetails(!showActivitiesDetails)}
                  className="w-full px-6 py-4 border-b flex items-center justify-between hover:bg-gray-50 transition"
                >
                  <div className="flex items-center gap-3">
                    <Activity className="w-5 h-5 text-gray-600" />
                    <div className="text-left">
                      <h3 className="text-lg font-semibold text-gray-900">
                        Recent Activities
                        {hubspotActivities.data.total_activities > 0 && 
                          ` (${hubspotActivities.data.total_activities})`
                        }
                      </h3>
                      <p className="text-sm text-gray-500">
                        Contact engagement and interactions
                      </p>
                    </div>
                  </div>
                  {showActivitiesDetails ? (
                    <ChevronUp className="w-5 h-5 text-gray-400" />
                  ) : (
                    <ChevronDown className="w-5 h-5 text-gray-400" />
                  )}
                </button>

                {showActivitiesDetails && (
                  <div className="p-6">
                    {hubspotActivities.data.error ? (
                      <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
                        <div className="flex items-center gap-2 text-yellow-800">
                          <AlertCircle className="w-5 h-5" />
                          <span className="font-medium">No activities available</span>
                        </div>
                        <p className="text-sm text-yellow-700 mt-2">
                          {hubspotActivities.data.error}
                        </p>
                      </div>
                    ) : hubspotActivities.data.activities && hubspotActivities.data.activities.length > 0 ? (
                      <div className="space-y-4">
                        {hubspotActivities.data.activities.map((activity, index) => (
                          <div key={index} className="border rounded-lg p-4 hover:shadow-md transition">
                            <div className="flex items-start gap-4">
                              <div className="w-10 h-10 bg-purple-100 rounded-full flex items-center justify-center flex-shrink-0">
                                <Activity className="w-5 h-5 text-purple-600" />
                              </div>
                              <div className="flex-1">
                                <div className="flex items-center justify-between mb-2">
                                  <h4 className="font-semibold text-gray-900">{activity.contact}</h4>
                                  <span className="text-xs text-gray-500">{activity.timestamp}</span>
                                </div>
                                <div className="flex items-center gap-2 mb-2">
                                  <span className="px-2 py-1 bg-blue-100 text-blue-800 text-xs font-medium rounded">
                                    {activity.type}
                                  </span>
                                </div>
                                <p className="text-sm text-gray-700 font-medium mb-1">{activity.subject}</p>
                                {activity.details && (
                                  <p className="text-sm text-gray-600">{activity.details}</p>
                                )}
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="text-center py-8 text-gray-500">
                        <Activity className="w-12 h-12 mx-auto mb-3 text-gray-300" />
                        <p>No activities found for this period</p>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}