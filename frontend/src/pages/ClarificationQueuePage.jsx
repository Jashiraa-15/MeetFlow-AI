import React, { useState, useEffect, useCallback } from 'react';
import { actionItemsApi } from '../api/client';
import { useWebSocket } from '../context/WebSocketContext';
import { ActionItemEditModal } from '../components/ActionItemEditModal';
import {
  HelpCircle,
  AlertTriangle,
  CheckCircle2,
  User,
  Calendar,
  Sparkles,
  Check,
  Edit2,
  Quote,
  ArrowRight
} from 'lucide-react';

export function ClarificationQueuePage() {
  const { subscribe } = useWebSocket();

  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Inline edit state for quick resolution: { [itemId]: { owner: '...', deadline: '...' } }
  const [inlineValues, setInlineValues] = useState({});
  const [savingId, setSavingId] = useState(null);

  const [editingItem, setEditingItem] = useState(null);

  const fetchClarificationItems = useCallback(async () => {
    setLoading(true);
    try {
      const data = await actionItemsApi.list({ needs_clarification: true });
      setItems(data);
      // Initialize inline values
      const map = {};
      data.forEach((i) => {
        map[i.id] = {
          owner: i.owner || '',
          deadline: i.deadline || '',
        };
      });
      setInlineValues(map);
      setError('');
    } catch (err) {
      console.error('Failed to load clarification queue:', err);
      setError('Unable to load clarification queue.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchClarificationItems();

    const unsubscribe = subscribe((event) => {
      if (
        event.event?.startsWith('action_item.') ||
        event.event?.startsWith('meeting.') ||
        event.event?.startsWith('clarification.')
      ) {
        fetchClarificationItems();
      }
    });

    return unsubscribe;
  }, [fetchClarificationItems, subscribe]);

  const handleInlineChange = (itemId, field, value) => {
    setInlineValues((prev) => ({
      ...prev,
      [itemId]: {
        ...prev[itemId],
        [field]: value,
      },
    }));
  };

  const handleResolve = async (item) => {
    const vals = inlineValues[item.id] || {};
    setSavingId(item.id);

    try {
      // 1. Update owner & deadline if modified
      const updates = {
        owner: vals.owner?.trim() || null,
        deadline: vals.deadline || null,
      };

      await actionItemsApi.update(item.id, updates);

      // 2. Confirm to resolve clarification
      await actionItemsApi.confirm(item.id);

      fetchClarificationItems();
    } catch (err) {
      alert(err.message || 'Failed to resolve action item.');
    } finally {
      setSavingId(null);
    }
  };

  return (
    <div className="clarification-page-view">
      {/* Header Banner */}
      <div className="clarification-banner">
        <div className="banner-icon-badge">
          <HelpCircle size={28} />
        </div>
        <div className="banner-text-group">
          <h1 className="banner-title">Needs Clarification Queue</h1>
          <p className="banner-subtitle">
            These action items were detected as ambiguous, missing an explicit owner, lacking a clear deadline, or having low AI confidence. Assign missing fields and confirm to clear the queue.
          </p>
        </div>
        <div className="banner-count-badge">
          <span className="count-number">{items.length}</span>
          <span className="count-label">Awaiting Clarification</span>
        </div>
      </div>

      {error && <div className="error-alert">{error}</div>}

      {/* Clarification Cards List */}
      {loading ? (
        <div className="page-loading-state">
          <div className="spinner" />
          <p>Scanning clarification queue...</p>
        </div>
      ) : items.length === 0 ? (
        <div className="dashboard-card mt-6">
          <div className="empty-state-large">
            <CheckCircle2 size={54} color="var(--success)" />
            <h3>Clarification Queue is Clear!</h3>
            <p>
              All extracted action items across your meetings have designated owners and confirmed deadlines.
            </p>
          </div>
        </div>
      ) : (
        <div className="clarification-cards-list">
          {items.map((item) => {
            const vals = inlineValues[item.id] || { owner: '', deadline: '' };
            const isSaving = savingId === item.id;

            return (
              <div key={item.id} className="clarification-card">
                <div className="card-top-row">
                  <div className="clarification-badge-group">
                    <span className="badge-clarify warning">
                      <AlertTriangle size={14} />
                      Action Item #{item.id}
                    </span>
                    <span className={`priority-badge ${item.priority?.toLowerCase() || 'medium'}`}>
                      {item.priority || 'Medium'}
                    </span>
                    <span className="category-tag">{item.category || 'General'}</span>
                    {item.confidence != null && (
                      <span className="confidence-pill">
                        Confidence: {Math.round(item.confidence * 100)}%
                      </span>
                    )}
                  </div>
                  <button
                    onClick={() => setEditingItem(item)}
                    className="btn btn-secondary btn-sm"
                  >
                    <Edit2 size={14} />
                    <span>Advanced Edit</span>
                  </button>
                </div>

                <h3 className="clarification-task-title">{item.task}</h3>

                {/* Source sentence quote */}
                {item.source_sentence && (
                  <div className="source-sentence-box">
                    <Quote size={16} className="quote-icon" />
                    <p className="source-text">"{item.source_sentence}"</p>
                  </div>
                )}

                {/* Quick Inline Resolution Form */}
                <div className="inline-resolution-form">
                  <div className="form-group flex-1">
                    <label className="form-label">
                      <User size={14} />
                      <span>Assign Owner</span>
                    </label>
                    <input
                      type="text"
                      placeholder="e.g. Priya, Sam"
                      value={vals.owner}
                      onChange={(e) => handleInlineChange(item.id, 'owner', e.target.value)}
                      className="form-input"
                      disabled={isSaving}
                    />
                  </div>

                  <div className="form-group flex-1">
                    <label className="form-label">
                      <Calendar size={14} />
                      <span>Set Target Deadline</span>
                    </label>
                    <input
                      type="date"
                      value={vals.deadline}
                      onChange={(e) => handleInlineChange(item.id, 'deadline', e.target.value)}
                      className="form-input"
                      disabled={isSaving}
                    />
                  </div>

                  <button
                    onClick={() => handleResolve(item)}
                    disabled={isSaving}
                    className="btn btn-primary btn-resolve"
                  >
                    {isSaving ? (
                      <span className="btn-loading">
                        <span className="spinner-sm" />
                        <span>Confirming...</span>
                      </span>
                    ) : (
                      <span className="btn-content">
                        <Check size={16} />
                        <span>Confirm & Resolve</span>
                      </span>
                    )}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Edit Modal */}
      {editingItem && (
        <ActionItemEditModal
          isOpen={!!editingItem}
          item={editingItem}
          onClose={() => setEditingItem(null)}
          onUpdated={fetchClarificationItems}
        />
      )}
    </div>
  );
}
