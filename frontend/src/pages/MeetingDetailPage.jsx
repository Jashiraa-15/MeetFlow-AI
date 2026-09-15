import React, { useState, useEffect, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import { meetingsApi, actionItemsApi, exportApi } from '../api/client';
import { useWebSocket } from '../context/WebSocketContext';
import { ActionItemEditModal } from '../components/ActionItemEditModal';
import { DuplicateMergeModal } from '../components/DuplicateMergeModal';
import {
  ArrowLeft,
  Calendar,
  FileDown,
  FileText,
  CheckSquare,
  FileCheck,
  AlertTriangle,
  ChevronDown,
  ChevronUp,
  Check,
  Edit2,
  GitMerge,
  Smile,
  Frown,
  Meh,
  Copy,
  Clock,
  Sparkles
} from 'lucide-react';

export function MeetingDetailPage() {
  const { id } = useParams();
  const { subscribe } = useWebSocket();

  const [meeting, setMeeting] = useState(null);
  const [recurringItems, setRecurringItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [transcriptExpanded, setTranscriptExpanded] = useState(true);
  const [exporting, setExporting] = useState(false);
  const [copied, setCopied] = useState(false);

  const [editingItem, setEditingItem] = useState(null);
  const [mergePrimaryItem, setMergePrimaryItem] = useState(null);

  const fetchMeetingData = useCallback(async () => {
    try {
      const [meetingData, recurringData] = await Promise.all([
        meetingsApi.getById(id),
        meetingsApi.getRecurring(id).catch(() => []),
      ]);
      setMeeting(meetingData);
      setRecurringItems(recurringData);
      setError('');
    } catch (err) {
      setError(err.message || 'Failed to load meeting details.');
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    fetchMeetingData();

    const unsubscribe = subscribe((event) => {
      if (
        event.event?.startsWith('meeting.') ||
        event.event?.startsWith('action_item.')
      ) {
        fetchMeetingData();
      }
    });

    return unsubscribe;
  }, [fetchMeetingData, subscribe]);

  const handleStatusChange = async (itemId, newStatus) => {
    try {
      await actionItemsApi.update(itemId, { status: newStatus });
      fetchMeetingData();
    } catch (err) {
      alert(err.message || 'Failed to update status.');
    }
  };

  const handleConfirm = async (itemId) => {
    try {
      await actionItemsApi.confirm(itemId);
      fetchMeetingData();
    } catch (err) {
      alert(err.message || 'Failed to confirm item.');
    }
  };

  const handleDownloadCsv = async () => {
    setExporting(true);
    try {
      await exportApi.downloadCsv(id, meeting?.title || 'meeting');
    } catch (err) {
      alert(err.message || 'CSV export failed.');
    } finally {
      setExporting(false);
    }
  };

  const handleDownloadPdf = async () => {
    setExporting(true);
    try {
      await exportApi.downloadPdf(id, meeting?.title || 'meeting');
    } catch (err) {
      alert(err.message || 'PDF export failed.');
    } finally {
      setExporting(false);
    }
  };

  const handleCopyTranscript = () => {
    if (meeting?.transcript_text) {
      navigator.clipboard.writeText(meeting.transcript_text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const getSentimentIcon = (sentiment) => {
    switch (sentiment?.toLowerCase()) {
      case 'positive':
      case 'smooth':
        return <Smile size={18} className="sentiment-icon positive" />;
      case 'negative':
      case 'blocked':
        return <Frown size={18} className="sentiment-icon negative" />;
      default:
        return <Meh size={18} className="sentiment-icon neutral" />;
    }
  };

  if (loading) {
    return (
      <div className="page-loading-state">
        <div className="spinner" />
        <p>Loading meeting intelligence...</p>
      </div>
    );
  }

  if (error || !meeting) {
    return (
      <div className="empty-state-large">
        <AlertTriangle size={48} color="var(--danger)" />
        <h3>Error Loading Meeting</h3>
        <p>{error || 'Meeting not found or you do not have permission to view it.'}</p>
        <Link to="/meetings" className="btn btn-secondary mt-4">
          &larr; Back to Meetings
        </Link>
      </div>
    );
  }

  return (
    <div className="meeting-detail-view">
      {/* Top Breadcrumb & Actions Bar */}
      <div className="detail-top-nav">
        <Link to="/meetings" className="btn-back">
          <ArrowLeft size={16} />
          <span>Back to Meetings</span>
        </Link>

        <div className="detail-export-actions">
          <button
            onClick={handleDownloadCsv}
            disabled={exporting}
            className="btn btn-secondary btn-sm"
          >
            <FileDown size={16} />
            <span>Export CSV</span>
          </button>
          <button
            onClick={handleDownloadPdf}
            disabled={exporting}
            className="btn btn-secondary btn-sm"
          >
            <FileText size={16} />
            <span>Export PDF</span>
          </button>
        </div>
      </div>

      {/* Meeting Overview Header */}
      <div className="detail-header-card">
        <div className="detail-title-section">
          <h1 className="detail-meeting-title">{meeting.title}</h1>
          <div className="detail-meta-pills">
            <span className="meta-pill">
              <Calendar size={14} />
              <span>{meeting.meeting_date}</span>
            </span>
            <span className="meta-pill sentiment">
              {getSentimentIcon(meeting.sentiment)}
              <span className="capitalize">{meeting.sentiment || 'neutral'}</span>
            </span>
            <span className="meta-pill">
              <CheckSquare size={14} />
              <span>{meeting.action_items?.length || 0} Action Items</span>
            </span>
            <span className="meta-pill">
              <FileCheck size={14} />
              <span>{meeting.decisions?.length || 0} Decisions</span>
            </span>
          </div>
        </div>
      </div>

      {/* Recurring Action Items Alert Banner */}
      {recurringItems.length > 0 && (
        <div className="alert-banner warning">
          <div className="alert-banner-content">
            <AlertTriangle size={20} className="alert-icon" />
            <div>
              <strong>Recurring Unresolved Tasks Detected ({recurringItems.length})</strong>
              <p>
                The following tasks were previously mentioned in earlier meetings and remain unresolved:
              </p>
              <ul className="recurring-list">
                {recurringItems.map((r) => (
                  <li key={r.id}>
                    "{r.task}" (Mentioned {r.mention_count} times)
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}

      {/* Collapsible Transcript Section */}
      <div className="dashboard-card mb-6">
        <div
          className="card-header-bar cursor-pointer"
          onClick={() => setTranscriptExpanded(!transcriptExpanded)}
        >
          <div className="card-title-group">
            <FileText size={18} className="card-header-icon" />
            <h3 className="card-title">Meeting Transcript</h3>
          </div>
          <div className="transcript-header-actions">
            <button
              onClick={(e) => {
                e.stopPropagation();
                handleCopyTranscript();
              }}
              className="btn btn-secondary btn-sm"
              title="Copy transcript text"
            >
              <Copy size={14} />
              <span>{copied ? 'Copied!' : 'Copy Text'}</span>
            </button>
            <button className="btn-toggle-expand" aria-label="Toggle transcript">
              {transcriptExpanded ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
            </button>
          </div>
        </div>

        {transcriptExpanded && (
          <div className="transcript-body-content">
            <pre className="transcript-pre-text">{meeting.transcript_text}</pre>
          </div>
        )}
      </div>

      {/* Extracted Action Items Section */}
      <div className="dashboard-card mb-6">
        <div className="card-header-bar">
          <div className="card-title-group">
            <CheckSquare size={18} className="card-header-icon" />
            <h3 className="card-title">
              Extracted Action Items ({meeting.action_items?.length || 0})
            </h3>
          </div>
        </div>

        <div className="table-responsive">
          {meeting.action_items && meeting.action_items.length > 0 ? (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Task Description</th>
                  <th>Owner</th>
                  <th>Deadline</th>
                  <th>Priority</th>
                  <th>Status</th>
                  <th>Clarification</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {meeting.action_items.map((item) => (
                  <tr key={item.id}>
                    <td className="task-cell">
                      <span className="task-text-title">{item.task}</span>
                      {item.source_sentence && (
                        <span className="task-source-quote" title="Source sentence from transcript">
                          "{item.source_sentence}"
                        </span>
                      )}
                    </td>
                    <td>
                      <span className={`owner-badge ${!item.owner ? 'unassigned' : ''}`}>
                        {item.owner || 'Unassigned'}
                      </span>
                    </td>
                    <td>
                      <span className="deadline-text">
                        {item.deadline ? item.deadline : <span className="text-muted">None</span>}
                      </span>
                    </td>
                    <td>
                      <span className={`priority-badge ${item.priority?.toLowerCase() || 'medium'}`}>
                        {item.priority || 'Medium'}
                      </span>
                    </td>
                    <td>
                      <select
                        value={item.status || 'todo'}
                        onChange={(e) => handleStatusChange(item.id, e.target.value)}
                        className={`status-dropdown status-${item.status || 'todo'}`}
                      >
                        <option value="todo">To Do</option>
                        <option value="in_progress">In Progress</option>
                        <option value="done">Done</option>
                      </select>
                    </td>
                    <td>
                      {item.needs_clarification ? (
                        <span className="badge-clarify warning">
                          <AlertTriangle size={12} />
                          Needs Clarification
                        </span>
                      ) : item.is_confirmed ? (
                        <span className="badge-clarify confirmed">
                          <Check size={12} />
                          Confirmed
                        </span>
                      ) : (
                        <span className="badge-clarify unconfirmed">Unconfirmed</span>
                      )}
                    </td>
                    <td>
                      <div className="action-button-group">
                        {!item.is_confirmed && (
                          <button
                            onClick={() => handleConfirm(item.id)}
                            className="btn btn-secondary btn-sm btn-icon"
                            title="Confirm Action Item"
                          >
                            <Check size={14} color="var(--success)" />
                          </button>
                        )}
                        <button
                          onClick={() => setEditingItem(item)}
                          className="btn btn-secondary btn-sm btn-icon"
                          title="Edit Action Item"
                        >
                          <Edit2 size={14} />
                        </button>
                        <button
                          onClick={() => setMergePrimaryItem(item)}
                          className="btn btn-secondary btn-sm btn-icon"
                          title="Check Duplicates & Merge"
                        >
                          <GitMerge size={14} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="empty-state-small">
              <p>No action items extracted from this meeting.</p>
            </div>
          )}
        </div>
      </div>

      {/* Extracted Decisions Section */}
      <div className="dashboard-card">
        <div className="card-header-bar">
          <div className="card-title-group">
            <FileCheck size={18} className="card-header-icon" />
            <h3 className="card-title">Decisions Made ({meeting.decisions?.length || 0})</h3>
          </div>
        </div>

        <div className="decisions-list-view">
          {meeting.decisions && meeting.decisions.length > 0 ? (
            meeting.decisions.map((dec) => (
              <div key={dec.id} className="decision-card">
                <div className="decision-icon-wrap">
                  <Check size={18} />
                </div>
                <div className="decision-content">
                  <h4 className="decision-text">{dec.decision_text}</h4>
                  {dec.context && <p className="decision-context">Context: {dec.context}</p>}
                </div>
              </div>
            ))
          ) : (
            <div className="empty-state-small">
              <p>No explicit decisions extracted from this meeting.</p>
            </div>
          )}
        </div>
      </div>

      {/* Modals */}
      {editingItem && (
        <ActionItemEditModal
          isOpen={!!editingItem}
          item={editingItem}
          onClose={() => setEditingItem(null)}
          onUpdated={fetchMeetingData}
        />
      )}

      {mergePrimaryItem && (
        <DuplicateMergeModal
          isOpen={!!mergePrimaryItem}
          primaryItem={mergePrimaryItem}
          onClose={() => setMergePrimaryItem(null)}
          onMerged={fetchMeetingData}
        />
      )}
    </div>
  );
}
