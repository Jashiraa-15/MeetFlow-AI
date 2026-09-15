import React, { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { decisionsApi, meetingsApi } from '../api/client';
import { useWebSocket } from '../context/WebSocketContext';
import {
  FileCheck,
  Check,
  FolderOpen,
  Calendar,
  Filter,
  Sparkles
} from 'lucide-react';

export function DecisionsPage() {
  const { subscribe } = useWebSocket();

  const [decisions, setDecisions] = useState([]);
  const [meetings, setMeetings] = useState([]);
  const [selectedMeetingId, setSelectedMeetingId] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const fetchDecisionsAndMeetings = useCallback(async () => {
    setLoading(true);
    try {
      const [decisionsData, meetingsData] = await Promise.all([
        decisionsApi.list(selectedMeetingId || null),
        meetingsApi.list({ pageSize: 100 }),
      ]);
      setDecisions(decisionsData);
      setMeetings(meetingsData.items || []);
      setError('');
    } catch (err) {
      console.error('Failed to load decisions:', err);
      setError('Unable to load decisions.');
    } finally {
      setLoading(false);
    }
  }, [selectedMeetingId]);

  useEffect(() => {
    fetchDecisionsAndMeetings();

    const unsubscribe = subscribe((event) => {
      if (event.event?.startsWith('meeting.')) {
        fetchDecisionsAndMeetings();
      }
    });

    return unsubscribe;
  }, [fetchDecisionsAndMeetings, subscribe]);

  return (
    <div className="decisions-page-view">
      <div className="page-header-row">
        <div>
          <h1 className="page-title">Executive Decisions Log</h1>
          <p className="page-subtitle">
            All strategic decisions and agreements detected during meetings.
          </p>
        </div>
      </div>

      {/* Filter by Meeting */}
      <div className="filter-card">
        <div className="filter-group flex-1">
          <label className="filter-label">Filter by Meeting</label>
          <div className="search-input-wrap">
            <FolderOpen size={16} className="search-icon" />
            <select
              value={selectedMeetingId}
              onChange={(e) => setSelectedMeetingId(e.target.value)}
              className="form-select filter-select"
            >
              <option value="">All Meetings ({meetings.length})</option>
              {meetings.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.title} ({m.meeting_date})
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Decisions List */}
      <div className="dashboard-card mt-4">
        {loading ? (
          <div className="page-loading-state">
            <div className="spinner-sm" />
            <span>Loading decisions...</span>
          </div>
        ) : decisions.length === 0 ? (
          <div className="empty-state-large">
            <FileCheck size={48} color="var(--primary)" />
            <h3>No Decisions Recorded</h3>
            <p>
              {selectedMeetingId
                ? 'No explicit decisions were recorded for this selected meeting.'
                : 'No decisions have been detected yet across your meetings.'}
            </p>
          </div>
        ) : (
          <div className="decisions-list-view">
            {decisions.map((dec) => (
              <div key={dec.id} className="decision-card">
                <div className="decision-icon-wrap">
                  <Check size={20} />
                </div>
                <div className="decision-content">
                  <h3 className="decision-text">{dec.decision_text}</h3>
                  {dec.context && (
                    <p className="decision-context">
                      <strong>Context:</strong> {dec.context}
                    </p>
                  )}
                  <div className="decision-footer-meta">
                    <Link to={`/meetings/${dec.meeting_id}`} className="decision-meeting-link">
                      <FolderOpen size={14} />
                      <span>Meeting #{dec.meeting_id}</span>
                    </Link>
                    {dec.created_at && (
                      <span className="decision-timestamp">
                        <Calendar size={14} />
                        <span>{new Date(dec.created_at).toLocaleDateString()}</span>
                      </span>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
