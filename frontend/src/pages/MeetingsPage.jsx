import React, { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { meetingsApi } from '../api/client';
import { useWebSocket } from '../context/WebSocketContext';
import {
  FolderOpen,
  Search,
  PlusCircle,
  Calendar,
  CheckSquare,
  FileCheck,
  Smile,
  Frown,
  Meh
} from 'lucide-react';

export function MeetingsPage() {
  const { subscribe } = useWebSocket();
  const [meetings, setMeetings] = useState([]);
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalCount, setTotalCount] = useState(0);
  const [loading, setLoading] = useState(true);

  const fetchMeetings = useCallback(async () => {
    setLoading(true);
    try {
      const data = await meetingsApi.list({ page, pageSize: 15, search: search.trim() || undefined });
      setMeetings(data.items || []);
      setTotalPages(data.total_pages || 1);
      setTotalCount(data.total || 0);
    } catch (err) {
      console.error('Failed to fetch meetings:', err);
    } finally {
      setLoading(false);
    }
  }, [page, search]);

  useEffect(() => {
    fetchMeetings();

    const unsubscribe = subscribe((event) => {
      if (event.event?.startsWith('meeting.')) {
        fetchMeetings();
      }
    });

    return unsubscribe;
  }, [fetchMeetings, subscribe]);

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    setPage(1);
    fetchMeetings();
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

  return (
    <div className="meetings-page-view">
      <div className="page-header-row">
        <div>
          <h1 className="page-title">Meetings Archive</h1>
          <p className="page-subtitle">
            Search transcripts and view AI-extracted action items & decisions.
          </p>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="filter-card">
        <form onSubmit={handleSearchSubmit} className="search-form">
          <div className="search-input-wrap">
            <Search size={18} className="search-icon" />
            <input
              type="text"
              placeholder="Search across meeting transcripts or action items..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="form-input search-input"
            />
          </div>
          <button type="submit" className="btn btn-secondary">
            Search
          </button>
        </form>
      </div>

      {/* Meetings Table */}
      <div className="dashboard-card mt-4">
        {loading ? (
          <div className="page-loading-state">
            <div className="spinner-sm" />
            <span>Loading meetings...</span>
          </div>
        ) : meetings.length === 0 ? (
          <div className="empty-state-large">
            <FolderOpen size={48} color="var(--primary)" />
            <h3>No meetings found</h3>
            <p>
              {search
                ? `No meetings match your search query "${search}".`
                : 'You have not processed any meeting transcripts yet.'}
            </p>
          </div>
        ) : (
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
                {meetings.map((m) => (
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
                      <span className="count-badge items">{m.action_item_count || 0} items</span>
                    </td>
                    <td>
                      <span className="count-badge decisions">{m.decision_count || 0} decisions</span>
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
        )}

        {/* Pagination Controls */}
        {totalPages > 1 && (
          <div className="pagination-bar">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="btn btn-secondary btn-sm"
            >
              Previous
            </button>
            <span className="pagination-info">
              Page {page} of {totalPages} ({totalCount} total)
            </span>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
              className="btn btn-secondary btn-sm"
            >
              Next
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
