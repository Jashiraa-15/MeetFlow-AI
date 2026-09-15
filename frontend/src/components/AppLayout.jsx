import React, { useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useWebSocket } from '../context/WebSocketContext';
import { ToastContainer } from './ToastContainer';
import { AddMeetingModal } from './AddMeetingModal';
import {
  LayoutDashboard,
  Calendar,
  CheckSquare,
  HelpCircle,
  FolderOpen,
  FileCheck,
  PlusCircle,
  LogOut,
  User as UserIcon,
  Wifi,
  WifiOff,
  Sparkles
} from 'lucide-react';

export function AppLayout({ children }) {
  const { user, logout } = useAuth();
  const { status } = useWebSocket();
  const [isAddMeetingOpen, setIsAddMeetingOpen] = useState(false);
  const navigate = useNavigate();

  const handleMeetingCreated = (newMeeting) => {
    // Navigate to meeting detail or refresh
    navigate(`/meetings/${newMeeting.id}`);
  };

  return (
    <div className="app-shell">
      {/* Sidebar Navigation */}
      <aside className="app-sidebar">
        <div className="sidebar-brand">
          <div className="brand-logo">
            <CheckSquare size={22} />
          </div>
          <div className="brand-texts">
            <span className="brand-main">MeetFlow AI</span>
            <span className="brand-badge-ai">AI-Powered</span>
          </div>
        </div>

        {/* Quick Action Button */}
        <div className="sidebar-action-wrap">
          <button
            onClick={() => setIsAddMeetingOpen(true)}
            className="btn btn-primary btn-block btn-new-meeting"
          >
            <PlusCircle size={18} />
            <span>New Meeting</span>
          </button>
        </div>

        {/* Nav Links */}
        <nav className="sidebar-nav">
          <NavLink
            to="/dashboard"
            className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
          >
            <LayoutDashboard size={18} />
            <span>Dashboard</span>
          </NavLink>

          <NavLink
            to="/meetings"
            className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
          >
            <FolderOpen size={18} />
            <span>Meetings</span>
          </NavLink>

          <NavLink
            to="/action-items"
            className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
          >
            <CheckSquare size={18} />
            <span>Action Items</span>
          </NavLink>

          <NavLink
            to="/clarifications"
            className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
          >
            <HelpCircle size={18} />
            <span>Clarification Queue</span>
          </NavLink>

          <NavLink
            to="/decisions"
            className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
          >
            <FileCheck size={18} />
            <span>Decisions</span>
          </NavLink>

          <NavLink
            to="/calendar"
            className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
          >
            <Calendar size={18} />
            <span>Calendar</span>
          </NavLink>
        </nav>

        {/* Sidebar Footer User Info */}
        <div className="sidebar-footer">
          <div className="sidebar-user-card">
            <div className="user-avatar">
              <UserIcon size={16} />
            </div>
            <div className="user-info">
              <span className="user-email-text" title={user?.email}>
                {user?.email || 'User'}
              </span>
              <span className="user-role-pill">{user?.role || 'member'}</span>
            </div>
          </div>
          <button onClick={logout} className="btn-logout" title="Sign Out">
            <LogOut size={16} />
          </button>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="app-main-wrapper">
        {/* Top Bar */}
        <header className="app-topbar">
          <div className="topbar-left">
            <span className="system-tagline">AI Meeting Extraction & Clarification System</span>
          </div>

          <div className="topbar-right">
            {/* Live WS Status Pill */}
            <div className={`ws-status-pill ${status}`}>
              {status === 'connected' ? (
                <>
                  <span className="status-dot connected" />
                  <span className="status-label">Live Sync</span>
                </>
              ) : status === 'connecting' ? (
                <>
                  <span className="status-dot connecting" />
                  <span className="status-label">Connecting...</span>
                </>
              ) : (
                <>
                  <span className="status-dot disconnected" />
                  <span className="status-label">Offline</span>
                </>
              )}
            </div>

            <button
              onClick={() => setIsAddMeetingOpen(true)}
              className="btn btn-primary btn-sm topbar-add-btn"
            >
              <Sparkles size={14} />
              <span>Add Transcript</span>
            </button>
          </div>
        </header>

        {/* View Content */}
        <main className="app-content-body">
          <div className="app-content-container">
            {children}
          </div>
        </main>
      </div>

      {/* Modals & Toasts */}
      <AddMeetingModal
        isOpen={isAddMeetingOpen}
        onClose={() => setIsAddMeetingOpen(false)}
        onMeetingCreated={handleMeetingCreated}
      />

      <ToastContainer />
    </div>
  );
}
