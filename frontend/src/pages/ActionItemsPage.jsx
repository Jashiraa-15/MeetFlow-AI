import React, { useState, useEffect, useCallback } from 'react';
import { actionItemsApi } from '../api/client';
import { useWebSocket } from '../context/WebSocketContext';
import { ActionItemEditModal } from '../components/ActionItemEditModal';
import { DuplicateMergeModal } from '../components/DuplicateMergeModal';
import {
  CheckSquare,
  Search,
  Filter,
  Check,
  Edit2,
  GitMerge,
  AlertTriangle,
  Clock,
  User,
  Tag
} from 'lucide-react';

export function ActionItemsPage() {
  const { subscribe } = useWebSocket();

  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Filter States
  const [statusFilter, setStatusFilter] = useState('');
  const [ownerFilter, setOwnerFilter] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [clarificationFilter, setClarificationFilter] = useState('');
  const [overdueFilter, setOverdueFilter] = useState(false);

  // Modals
  const [editingItem, setEditingItem] = useState(null);
  const [mergePrimaryItem, setMergePrimaryItem] = useState(null);

  const fetchActionItems = useCallback(async () => {
    setLoading(true);
    try {
      const filters = {};
      if (statusFilter) filters.status = statusFilter;
      if (ownerFilter.trim()) filters.owner = ownerFilter.trim();
      if (categoryFilter) filters.category = categoryFilter;
      if (clarificationFilter !== '') filters.needs_clarification = clarificationFilter === 'true';
      if (overdueFilter) filters.overdue = true;

      const data = await actionItemsApi.list(filters);
      setItems(data);
      setError('');
    } catch (err) {
      console.error('Failed to load action items:', err);
      setError('Unable to load action items.');
    } finally {
      setLoading(false);
    }
  }, [statusFilter, ownerFilter, categoryFilter, clarificationFilter, overdueFilter]);

  useEffect(() => {
    fetchActionItems();

    const unsubscribe = subscribe((event) => {
      if (
        event.event?.startsWith('action_item.') ||
        event.event?.startsWith('meeting.')
      ) {
        fetchActionItems();
      }
    });

    return unsubscribe;
  }, [fetchActionItems, subscribe]);

  const handleStatusChange = async (itemId, newStatus) => {
    try {
      await actionItemsApi.update(itemId, { status: newStatus });
      fetchActionItems();
    } catch (err) {
      alert(err.message || 'Failed to update status.');
    }
  };

  const handleConfirm = async (itemId) => {
    try {
      await actionItemsApi.confirm(itemId);
      fetchActionItems();
    } catch (err) {
      alert(err.message || 'Failed to confirm item.');
    }
  };

  const clearFilters = () => {
    setStatusFilter('');
    setOwnerFilter('');
    setCategoryFilter('');
    setClarificationFilter('');
    setOverdueFilter(false);
  };

  return (
    <div className="action-items-page-view">
      <div className="page-header-row">
        <div>
          <h1 className="page-title">Action Items Directory</h1>
          <p className="page-subtitle">
            Manage, assign, update, confirm, and merge action items across all meetings.
          </p>
        </div>
      </div>

      {/* Filter Toolbar */}
      <div className="filter-card">
        <div className="filter-grid">
          {/* Status Filter */}
          <div className="filter-group">
            <label className="filter-label">Status</label>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="form-select filter-select"
            >
              <option value="">All Statuses</option>
              <option value="todo">To Do</option>
              <option value="in_progress">In Progress</option>
              <option value="done">Done</option>
            </select>
          </div>

          {/* Category Filter */}
          <div className="filter-group">
            <label className="filter-label">Category</label>
            <select
              value={categoryFilter}
              onChange={(e) => setCategoryFilter(e.target.value)}
              className="form-select filter-select"
            >
              <option value="">All Categories</option>
              <option value="Engineering">Engineering</option>
              <option value="Marketing">Marketing</option>
              <option value="General">General</option>
            </select>
          </div>

          {/* Clarification Filter */}
          <div className="filter-group">
            <label className="filter-label">Clarification</label>
            <select
              value={clarificationFilter}
              onChange={(e) => setClarificationFilter(e.target.value)}
              className="form-select filter-select"
            >
              <option value="">All Items</option>
              <option value="true">Needs Clarification</option>
              <option value="false">Clarified / Clear</option>
            </select>
          </div>

          {/* Owner Filter */}
          <div className="filter-group flex-1">
            <label className="filter-label">Filter by Owner</label>
            <div className="search-input-wrap">
              <User size={16} className="search-icon" />
              <input
                type="text"
                placeholder="e.g. Priya, Sam"
                value={ownerFilter}
                onChange={(e) => setOwnerFilter(e.target.value)}
                className="form-input search-input"
              />
            </div>
          </div>

          {/* Overdue Toggle */}
          <div className="filter-group filter-checkbox-group">
            <label className="checkbox-label mt-auto">
              <input
                type="checkbox"
                checked={overdueFilter}
                onChange={(e) => setOverdueFilter(e.target.checked)}
              />
              <span className="text-danger font-medium">Overdue Only</span>
            </label>
          </div>
        </div>

        {(statusFilter || ownerFilter || categoryFilter || clarificationFilter || overdueFilter) && (
          <div className="active-filters-bar">
            <span>Active filters applied</span>
            <button onClick={clearFilters} className="btn-link-action">
              Reset Filters
            </button>
          </div>
        )}
      </div>

      {/* Action Items List Table */}
      <div className="dashboard-card mt-4">
        {loading ? (
          <div className="page-loading-state">
            <div className="spinner-sm" />
            <span>Loading action items...</span>
          </div>
        ) : items.length === 0 ? (
          <div className="empty-state-large">
            <CheckSquare size={48} color="var(--primary)" />
            <h3>No action items found</h3>
            <p>Try adjusting your search filters or ingest a new meeting transcript.</p>
          </div>
        ) : (
          <div className="table-responsive">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Task Description</th>
                  <th>Owner</th>
                  <th>Deadline</th>
                  <th>Priority</th>
                  <th>Category</th>
                  <th>Status</th>
                  <th>Clarification</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.id}>
                    <td className="task-cell">
                      <span className="task-text-title">{item.task}</span>
                      <div className="task-meta-sub">
                        {item.mention_count > 1 && (
                          <span className="mention-pill" title="Mentioned in multiple meetings">
                            {item.mention_count}x Mentions
                          </span>
                        )}
                        {item.confidence != null && (
                          <span className="confidence-pill" title="AI Extraction Confidence Score">
                            {Math.round(item.confidence * 100)}% Conf
                          </span>
                        )}
                      </div>
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
                      <span className="category-tag">{item.category || 'General'}</span>
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
          </div>
        )}
      </div>

      {/* Modals */}
      {editingItem && (
        <ActionItemEditModal
          isOpen={!!editingItem}
          item={editingItem}
          onClose={() => setEditingItem(null)}
          onUpdated={fetchActionItems}
        />
      )}

      {mergePrimaryItem && (
        <DuplicateMergeModal
          isOpen={!!mergePrimaryItem}
          primaryItem={mergePrimaryItem}
          onClose={() => setMergePrimaryItem(null)}
          onMerged={fetchActionItems}
        />
      )}
    </div>
  );
}
