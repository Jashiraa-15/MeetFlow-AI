import React, { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { statsApi, meetingsApi, actionItemsApi } from '../api/client';
import { useWebSocket } from '../context/WebSocketContext';
import { ActionItemEditModal } from '../components/ActionItemEditModal';
import { AddMeetingModal } from '../components/AddMeetingModal';
import {
  FolderOpen,
  CheckSquare,
  AlertTriangle,
  HelpCircle,
  TrendingUp,
  ArrowRight,
  Clock,
  User,
  Sparkles,
  Calendar,
  Check,
  Smile,
  Frown,
  Meh
} from 'lucide-react';

export function DashboardPage() {
  const { subscribe } = useWebSocket();

  const [stats, setStats] = useState(null);
  const [recentMeetings, setRecentMeetings] = useState([]);
  const [clarificationItems, setClarificationItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const [editingItem, setEditingItem] = useState(null);
  const [isAddMeetingOpen, setIsAddMeetingOpen] = useState(false);

  const fetchDashboardData = useCallback(async () => {
    try {
      const [statsData, meetingsData, clarData] = await Promise.all([
        statsApi.getStats(),
        meetingsApi.list({ page: 1, pageSize: 5 }),
        actionItemsApi.list({ needs_clarification: true }),
      ]);

      setStats(statsData);
      setRecentMeetings(meetingsData.items || []);
      setClarificationItems(clarData.slice(0, 5));
      setError('');
    } catch (err) {
      console.error('Failed to load dashboard data:', err);
      setError('Unable to load dashboard data.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDashboardData();

    // Subscribe to real-time events to refresh automatically
    const unsubscribe = subscribe((event) => {
      if (
        event.event?.startsWith('meeting.') ||
        event.event?.startsWith('action_item.') ||
        event.event?.startsWith('clarification.')
      ) {
        fetchDashboardData();
      }
    });

    return unsubscribe;
  }, [fetchDashboardData, subscribe]);

  const handleQuickConfirm = async (item) => {
    try {
      await actionItemsApi.confirm(item.id);
      fetchDashboardData();
    } catch (err) {
      alert(err.message || 'Failed to confirm item.');
    }
  };

  const getSentimentIcon = (sentiment) => {
    switch (sentiment?.toLowerCase()) {
      case 'positive':
      case 'smooth':
        return <Smile size={16} className="sentiment-icon positive" />;
      case 'negative':
      case 'blocked':
        return <Frown size={16} className="sentiment-icon negative" />;
      default:
        return <Meh size={16} className="sentiment-icon neutral" />;
    }
  };

  if (loading) {
    return (
      <div className="page-loading-state">
        <div className="spinner" />
        <p>Loading your dashboard metrics...</p>
      </div>
    );
  }

  return (
    <div className="dashboard-view-page">
      {/* Page Header */}
      <div className="page-header-row">
        <div>
          <h1 className="page-title">Executive Dashboard</h1>
          <p className="page-subtitle">
            Real-time meeting intelligence, action-item tracking, and clarification queue.
          </p>
        </div>
      </div>

      {error && <div className="error-alert">{error}</div>}

      {/* Top 4 Stat Cards */}
      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-icon-wrap stat-meetings">
            <FolderOpen size={22} />
          </div>
          <div className="stat-details">
            <span className="stat-label">Total Meetings</span>
            <span className="stat-number">{stats?.total_meetings || 0}</span>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon-wrap stat-items">
            <CheckSquare size={22} />
          </div>
          <div className="stat-details">
            <span className="stat-label">Action Items</span>
            <span className="stat-number">{stats?.total_action_items || 0}</span>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon-wrap stat-clarification">
            <HelpCircle size={22} />
          </div>
          <div className="stat-details">
            <span className="stat-label">Clarification Rate</span>
            <span className="stat-number">
              {stats?.clarification_percentage != null
                ? `${stats.clarification_percentage}%`
                : '0%'}
            </span>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon-wrap stat-overdue">
            <AlertTriangle size={22} />
          </div>
          <div className="stat-details">
            <span className="stat-label">Overdue Tasks</span>
            <span className="stat-number text-danger">{stats?.overdue_count || 0}</span>
          </div>
        </div>
      </div>

      {/* Two-Column Middle Grid */}
      <div className="dashboard-middle-grid">
        {/* Workload Breakdown */}
        <div className="dashboard-card">
          <div className="card-header-bar">
            <div className="card-title-group">
              <TrendingUp size={18} className="card-header-icon" />
              <h3 className="card-title">Team Workload Distribution</h3>
            </div>
            <Link to="/action-items" className="card-header-link">
              View All Tasks &rarr;
            </Link>
          </div>

          <div className="workload-list">
            {stats?.workload && stats.workload.length > 0 ? (
              stats.workload.map((w) => {
                const total = stats.total_action_items || 1;
                const pct = Math.round((w.task_count / total) * 100);
                return (
                  <div key={w.owner} className="workload-item">
                    <div className="workload-meta">
                      <span className="workload-owner">
                        <User size={14} />
                        {w.owner}
                      </span>
                      <span className="workload-count">
                        {w.task_count} tasks ({pct}%)
                      </span>
                    </div>
                    <div className="workload-bar-bg">
                      <div className="workload-bar-fill" style={{ width: `${pct}%` }} />
                    </div>
                  </div>
                );
              })
            ) : (
              <div className="empty-state-small">
                <p>No assigned tasks yet. Process a meeting transcript to extract action items.</p>
              </div>
            )}
          </div>
        </div>

        {/* Priority Clarification Queue Preview */}
        <div className="dashboard-card">
          <div className="card-header-bar">
            <div className="card-title-group">
              <HelpCircle size={18} className="card-header-icon text-warning" />
              <h3 className="card-title">Needs Clarification Queue</h3>
              {clarificationItems.length > 0 && (
                <span className="badge-count-pill">{clarificationItems.length}</span>
              )}
            </div>
            <Link to="/clarifications" className="card-header-link">
              Open Queue &rarr;
            </Link>
          </div>

          <div className="clarification-mini-list">
            {clarificationItems.length > 0 ? (
              clarificationItems.map((item) => (
                <div key={item.id} className="clarification-mini-card">
                  <div className="clarification-mini-info">
                    <span className="clarification-task-text">{item.task}</span>
                    <div className="clarification-tags">
                      <span className="tag-warning">Missing Owner or Date</span>
                      {item.confidence && (
                        <span className="tag-muted">
                          Conf: {Math.round(item.confidence * 100)}%
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="clarification-mini-actions">
                    <button
                      onClick={() => setEditingItem(item)}
                      className="btn btn-secondary btn-sm"
                    >
                      Edit
                    </button>
                    <button
                      onClick={() => handleQuickConfirm(item)}
                      className="btn btn-primary btn-sm"
                      title="Confirm this item"
                    >
                      <Check size={14} />
                    </button>
                  </div>
                </div>
              ))
            ) : (
              <div className="empty-state-small">
                <Check size={24} color="var(--success)" />
                <p>All action items are fully specified and confirmed!</p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Recent Meetings Table / Sample Demo Transcript State */}
      <div className="dashboard-card mt-6">
        <div className="card-header-bar">
          <div className="card-title-group">
            <FolderOpen size={18} className="card-header-icon" />
            <h3 className="card-title">Recent Ingested Meetings</h3>
          </div>
          {recentMeetings.length > 0 && (
            <Link to="/meetings" className="card-header-link">
              All Meetings &rarr;
            </Link>
          )}
        </div>

        {recentMeetings.length > 0 ? (
          <div className="table-responsive">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Meeting Title</th>
                  <th>Date</th>
                  <th>Sentiment</th>
                  <th>Action Items</th>
                  <th>Decisions</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {recentMeetings.map((m) => (
                  <tr key={m.id}>
                    <td>
                      <Link to={`/meetings/${m.id}`} className="table-primary-link">
                        {m.title}
                      </Link>
                    </td>
                    <td>{m.meeting_date}</td>
                    <td>
                      <span className="sentiment-tag">
                        {getSentimentIcon(m.sentiment)}
                        <span className="capitalize">{m.sentiment || 'neutral'}</span>
                      </span>
                    </td>
                    <td>
                      <span className="count-badge items">{m.action_item_count || 0}</span>
                    </td>
                    <td>
                      <span className="count-badge decisions">{m.decision_count || 0}</span>
                    </td>
                    <td>
                      <Link to={`/meetings/${m.id}`} className="btn btn-secondary btn-sm">
                        View Details
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="demo-transcript-card">
            <div className="demo-card-header">
              <div className="demo-header-meta">
                <span className="demo-section-tag">MEETING TRANSCRIPT</span>
                <h3 className="demo-meeting-title">Q3 Product Launch Sync</h3>
                <div className="demo-sub-meta">
                  <span className="demo-meta-item">
                    <Calendar size={13} />
                    <span>Today</span>
                  </span>
                  <span className="demo-meta-dot">•</span>
                  <span className="demo-meta-item">
                    <User size={13} />
                    <span>Product Team (Priya, Rahul, Sam)</span>
                  </span>
                </div>
              </div>
              <div className="demo-badge-wrap">
                <span className="sample-badge">
                  <Sparkles size={13} />
                  <span>SAMPLE TRANSCRIPT</span>
                </span>
              </div>
            </div>

            <div className="demo-card-body">
              <div className="demo-transcript-dialogue">
                <div className="dialogue-line">
                  <span className="speaker-name priya">Priya:</span>
                  <p className="speaker-text">
                    Good morning everyone. Let's review the Q3 product launch timeline and make sure we're clear on the remaining tasks.
                  </p>
                </div>
                <div className="dialogue-line">
                  <span className="speaker-name rahul">Rahul:</span>
                  <p className="speaker-text">
                    I'll update the deployment checklist and make sure everything is ready for testing.
                  </p>
                </div>
                <div className="dialogue-line">
                  <span className="speaker-name sam">Sam:</span>
                  <p className="speaker-text">
                    What about the pricing page? It still needs to be updated before the launch.
                  </p>
                </div>
                <div className="dialogue-line">
                  <span className="speaker-name priya">Priya:</span>
                  <p className="speaker-text">
                    Sam, please handle the pricing page and complete it by Thursday.
                  </p>
                </div>
                <div className="dialogue-line">
                  <span className="speaker-name rahul">Rahul:</span>
                  <p className="speaker-text">
                    I'll also coordinate with the testing team to verify the final build.
                  </p>
                </div>
                <div className="dialogue-line">
                  <span className="speaker-name priya">Priya:</span>
                  <p className="speaker-text">
                    Perfect. Let's finalize everything by Friday.
                  </p>
                </div>
              </div>

              <div className="demo-insights-panel">
                <div>
                  <div className="insights-header">
                    <Sparkles size={16} className="insights-icon" />
                    <span className="insights-title">AI EXTRACTED INSIGHTS</span>
                  </div>

                  <div className="insights-metrics-list mt-4">
                    <div className="insight-metric-item success">
                      <CheckSquare size={16} />
                      <span>5 Action Items</span>
                    </div>
                    <div className="insight-metric-item success">
                      <Check size={16} />
                      <span>2 Decisions</span>
                    </div>
                    <div className="insight-metric-item warning">
                      <AlertTriangle size={16} />
                      <span>2 Need Clarification</span>
                    </div>
                  </div>
                </div>

                <div className="demo-card-actions">
                  <button
                    onClick={() => setIsAddMeetingOpen(true)}
                    className="btn btn-primary btn-sm btn-block"
                  >
                    <Sparkles size={14} />
                    <span>Process Sample Transcript &rarr;</span>
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Edit Modal */}
      {editingItem && (
        <ActionItemEditModal
          isOpen={!!editingItem}
          item={editingItem}
          onClose={() => setEditingItem(null)}
          onUpdated={fetchDashboardData}
        />
      )}

      {/* Ingestion Modal for Demo Sample */}
      <AddMeetingModal
        isOpen={isAddMeetingOpen}
        onClose={() => setIsAddMeetingOpen(false)}
        onMeetingCreated={() => {
          setIsAddMeetingOpen(false);
          fetchDashboardData();
        }}
      />
    </div>
  );
}
