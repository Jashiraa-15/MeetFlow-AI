import React, { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { calendarApi, actionItemsApi } from '../api/client';
import { useWebSocket } from '../context/WebSocketContext';
import { ActionItemEditModal } from '../components/ActionItemEditModal';
import {
  Calendar as CalendarIcon,
  CheckSquare,
  Clock,
  AlertTriangle,
  CheckCircle2,
  User,
  Check,
  Edit2
} from 'lucide-react';

export function CalendarPage() {
  const { subscribe } = useWebSocket();

  const [calendarData, setCalendarData] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const [editingItem, setEditingItem] = useState(null);

  const fetchCalendar = useCallback(async () => {
    setLoading(true);
    try {
      const data = await calendarApi.getCalendar();
      setCalendarData(data || {});
      setError('');
    } catch (err) {
      console.error('Failed to load calendar data:', err);
      setError('Unable to load calendar timeline.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchCalendar();

    const unsubscribe = subscribe((event) => {
      if (
        event.event?.startsWith('action_item.') ||
        event.event?.startsWith('meeting.')
      ) {
        fetchCalendar();
      }
    });

    return unsubscribe;
  }, [fetchCalendar, subscribe]);

  const handleQuickStatus = async (itemId, newStatus) => {
    try {
      await actionItemsApi.update(itemId, { status: newStatus });
      fetchCalendar();
    } catch (err) {
      alert(err.message || 'Failed to update status.');
    }
  };

  const todayStr = new Date().toISOString().split('T')[0];
  const dateKeys = Object.keys(calendarData).sort();

  const getItemUrgencyClass = (deadline, status) => {
    if (status === 'done') return 'item-done';
    if (deadline < todayStr) return 'item-overdue';
    if (deadline === todayStr) return 'item-today';
    return 'item-upcoming';
  };

  const getUrgencyBadge = (deadline, status) => {
    if (status === 'done') {
      return (
        <span className="urgency-badge done">
          <CheckCircle2 size={12} />
          Completed
        </span>
      );
    }
    if (deadline < todayStr) {
      return (
        <span className="urgency-badge overdue">
          <AlertTriangle size={12} />
          Overdue
        </span>
      );
    }
    if (deadline === todayStr) {
      return (
        <span className="urgency-badge today">
          <Clock size={12} />
          Due Today
        </span>
      );
    }
    return (
      <span className="urgency-badge upcoming">
        <Clock size={12} />
        Upcoming
      </span>
    );
  };

  return (
    <div className="calendar-page-view">
      <div className="page-header-row">
        <div>
          <h1 className="page-title">Deadline Timeline & Calendar</h1>
          <p className="page-subtitle">
            All assigned action items grouped chronologically by deadline date.
          </p>
        </div>
      </div>

      {error && <div className="error-alert">{error}</div>}

      {loading ? (
        <div className="page-loading-state">
          <div className="spinner" />
          <p>Organizing timeline...</p>
        </div>
      ) : dateKeys.length === 0 ? (
        <div className="dashboard-card mt-4">
          <div className="empty-state-large">
            <CalendarIcon size={48} color="var(--primary)" />
            <h3>No Deadlines Scheduled</h3>
            <p>Action items with scheduled deadlines will appear here automatically.</p>
          </div>
        </div>
      ) : (
        <div className="calendar-timeline-container">
          {dateKeys.map((dateStr) => {
            const items = calendarData[dateStr] || [];
            const isPast = dateStr < todayStr;
            const isToday = dateStr === todayStr;

            return (
              <div key={dateStr} className={`timeline-day-block ${isToday ? 'today' : isPast ? 'past' : 'future'}`}>
                {/* Date Header Header */}
                <div className="timeline-date-header">
                  <div className="date-badge-wrap">
                    <CalendarIcon size={16} />
                    <span className="timeline-date-title">{dateStr}</span>
                    {isToday && <span className="pill-today">TODAY</span>}
                  </div>
                  <span className="timeline-task-count">
                    {items.length} {items.length === 1 ? 'task' : 'tasks'}
                  </span>
                </div>

                {/* Day's Tasks */}
                <div className="timeline-tasks-grid">
                  {items.map((item) => (
                    <div
                      key={item.id}
                      className={`calendar-task-card ${getItemUrgencyClass(item.deadline, item.status)}`}
                    >
                      <div className="card-top">
                        {getUrgencyBadge(item.deadline, item.status)}
                        <span className={`priority-badge ${item.priority?.toLowerCase() || 'medium'}`}>
                          {item.priority || 'Medium'}
                        </span>
                      </div>

                      <h4 className={`calendar-task-text ${item.status === 'done' ? 'line-through' : ''}`}>
                        {item.task}
                      </h4>

                      <div className="calendar-meta-row">
                        <span className="owner-badge-small">
                          <User size={12} />
                          {item.owner || 'Unassigned'}
                        </span>
                        <span className="category-tag">{item.category || 'General'}</span>
                        <Link to={`/meetings/${item.meeting_id}`} className="meeting-ref-link">
                          Meeting #{item.meeting_id}
                        </Link>
                      </div>

                      <div className="card-bottom-actions">
                        <select
                          value={item.status || 'todo'}
                          onChange={(e) => handleQuickStatus(item.id, e.target.value)}
                          className={`status-dropdown status-${item.status || 'todo'}`}
                        >
                          <option value="todo">To Do</option>
                          <option value="in_progress">In Progress</option>
                          <option value="done">Done</option>
                        </select>

                        <button
                          onClick={() => setEditingItem(item)}
                          className="btn btn-secondary btn-sm"
                          title="Edit Task Details"
                        >
                          <Edit2 size={12} />
                          <span>Edit</span>
                        </button>
                      </div>
                    </div>
                  ))}
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
          onUpdated={fetchCalendar}
        />
      )}
    </div>
  );
}
