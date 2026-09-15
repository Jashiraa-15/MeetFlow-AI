import React, { useState, useEffect } from 'react';
import { actionItemsApi } from '../api/client';
import { X, Check, AlertCircle } from 'lucide-react';

export function ActionItemEditModal({ isOpen, item, onClose, onUpdated }) {
  const [task, setTask] = useState('');
  const [owner, setOwner] = useState('');
  const [deadline, setDeadline] = useState('');
  const [priority, setPriority] = useState('Medium');
  const [category, setCategory] = useState('General');
  const [status, setStatus] = useState('todo');
  const [needsClarification, setNeedsClarification] = useState(false);
  const [isConfirmed, setIsConfirmed] = useState(false);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (item) {
      setTask(item.task || '');
      setOwner(item.owner || '');
      setDeadline(item.deadline || '');
      setPriority(item.priority || 'Medium');
      setCategory(item.category || 'General');
      setStatus(item.status || 'todo');
      setNeedsClarification(!!item.needs_clarification);
      setIsConfirmed(!!item.is_confirmed);
      setError('');
    }
  }, [item]);

  if (!isOpen || !item) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    if (!task.trim()) {
      setError('Task title cannot be empty.');
      return;
    }

    setLoading(true);
    try {
      const updates = {
        task: task.trim(),
        owner: owner.trim() || null,
        deadline: deadline || null,
        priority,
        category,
        status,
        needs_clarification: needsClarification,
        is_confirmed: isConfirmed,
      };

      const updated = await actionItemsApi.update(item.id, updates);
      if (onUpdated) {
        onUpdated(updated);
      }
      onClose();
    } catch (err) {
      setError(err.message || 'Failed to update action item.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-container modal-md" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2 className="modal-title">Edit Action Item #{item.id}</h2>
          <button onClick={onClose} className="modal-close-btn" aria-label="Close modal">
            <X size={18} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="modal-form">
          {error && (
            <div className="error-alert">
              <AlertCircle size={18} className="error-icon" />
              <span>{error}</span>
            </div>
          )}

          <div className="form-group">
            <label className="form-label">Task Description</label>
            <input
              type="text"
              value={task}
              onChange={(e) => setTask(e.target.value)}
              className="form-input"
              required
              disabled={loading}
            />
          </div>

          <div className="form-row">
            <div className="form-group flex-1">
              <label className="form-label">Owner</label>
              <input
                type="text"
                placeholder="e.g. Priya"
                value={owner}
                onChange={(e) => setOwner(e.target.value)}
                className="form-input"
                disabled={loading}
              />
            </div>

            <div className="form-group flex-1">
              <label className="form-label">Deadline</label>
              <input
                type="date"
                value={deadline}
                onChange={(e) => setDeadline(e.target.value)}
                className="form-input"
                disabled={loading}
              />
            </div>
          </div>

          <div className="form-row">
            <div className="form-group flex-1">
              <label className="form-label">Priority</label>
              <select
                value={priority}
                onChange={(e) => setPriority(e.target.value)}
                className="form-select"
                disabled={loading}
              >
                <option value="High">High</option>
                <option value="Medium">Medium</option>
                <option value="Low">Low</option>
              </select>
            </div>

            <div className="form-group flex-1">
              <label className="form-label">Category</label>
              <select
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                className="form-select"
                disabled={loading}
              >
                <option value="Engineering">Engineering</option>
                <option value="Marketing">Marketing</option>
                <option value="General">General</option>
              </select>
            </div>

            <div className="form-group flex-1">
              <label className="form-label">Status</label>
              <select
                value={status}
                onChange={(e) => setStatus(e.target.value)}
                className="form-select"
                disabled={loading}
              >
                <option value="todo">To Do</option>
                <option value="in_progress">In Progress</option>
                <option value="done">Done</option>
              </select>
            </div>
          </div>

          <div className="form-row checkboxes-row">
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={needsClarification}
                onChange={(e) => setNeedsClarification(e.target.checked)}
                disabled={loading}
              />
              <span>Needs Clarification</span>
            </label>

            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={isConfirmed}
                onChange={(e) => setIsConfirmed(e.target.checked)}
                disabled={loading}
              />
              <span>Confirmed</span>
            </label>
          </div>

          <div className="modal-footer">
            <button type="button" onClick={onClose} className="btn btn-secondary" disabled={loading}>
              Cancel
            </button>
            <button type="submit" className="btn btn-primary" disabled={loading}>
              {loading ? 'Saving...' : 'Save Changes'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
