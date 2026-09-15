import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { WebSocketProvider } from './context/WebSocketContext';
import { ProtectedRoute } from './components/ProtectedRoute';
import { AppLayout } from './components/AppLayout';

import { AuthPage } from './pages/AuthPage';
import { DashboardPage } from './pages/DashboardPage';
import { MeetingsPage } from './pages/MeetingsPage';
import { MeetingDetailPage } from './pages/MeetingDetailPage';
import { ActionItemsPage } from './pages/ActionItemsPage';
import { ClarificationQueuePage } from './pages/ClarificationQueuePage';
import { DecisionsPage } from './pages/DecisionsPage';
import { CalendarPage } from './pages/CalendarPage';

export default function App() {
  return (
    <AuthProvider>
      <WebSocketProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="/login" element={<AuthPage initialMode="login" />} />
            <Route path="/register" element={<AuthPage initialMode="register" />} />

            {/* Protected Application Routes */}
            <Route
              path="/dashboard"
              element={
                <ProtectedRoute>
                  <AppLayout>
                    <DashboardPage />
                  </AppLayout>
                </ProtectedRoute>
              }
            />

            <Route
              path="/meetings"
              element={
                <ProtectedRoute>
                  <AppLayout>
                    <MeetingsPage />
                  </AppLayout>
                </ProtectedRoute>
              }
            />

            <Route
              path="/meetings/:id"
              element={
                <ProtectedRoute>
                  <AppLayout>
                    <MeetingDetailPage />
                  </AppLayout>
                </ProtectedRoute>
              }
            />

            <Route
              path="/action-items"
              element={
                <ProtectedRoute>
                  <AppLayout>
                    <ActionItemsPage />
                  </AppLayout>
                </ProtectedRoute>
              }
            />

            <Route
              path="/clarifications"
              element={
                <ProtectedRoute>
                  <AppLayout>
                    <ClarificationQueuePage />
                  </AppLayout>
                </ProtectedRoute>
              }
            />

            <Route
              path="/decisions"
              element={
                <ProtectedRoute>
                  <AppLayout>
                    <DecisionsPage />
                  </AppLayout>
                </ProtectedRoute>
              }
            />

            <Route
              path="/calendar"
              element={
                <ProtectedRoute>
                  <AppLayout>
                    <CalendarPage />
                  </AppLayout>
                </ProtectedRoute>
              }
            />

            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Routes>
        </BrowserRouter>
      </WebSocketProvider>
    </AuthProvider>
  );
}
