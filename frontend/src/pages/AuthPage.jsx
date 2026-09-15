import React, { useState } from 'react';
import { useNavigate, useLocation, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { CheckSquare, Lock, Mail, AlertCircle, ArrowRight, ShieldCheck } from 'lucide-react';

export function AuthPage({ initialMode = 'login' }) {
  const isRegister = initialMode === 'register';
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const { login, register } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const from = location.state?.from?.pathname || '/dashboard';

  const validate = () => {
    if (!email.trim()) {
      setError('Please enter your email address.');
      return false;
    }
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email.trim())) {
      setError('Please enter a valid email address.');
      return false;
    }
    if (!password) {
      setError('Please enter your password.');
      return false;
    }
    if (password.length < 6) {
      setError('Password must be at least 6 characters long.');
      return false;
    }
    if (isRegister && password !== confirmPassword) {
      setError('Passwords do not match. Please re-enter.');
      return false;
    }
    return true;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    if (!validate()) {
      return;
    }

    setIsSubmitting(true);
    try {
      if (isRegister) {
        await register(email.trim(), password);
      } else {
        await login(email.trim(), password);
      }
      navigate(from, { replace: true });
    } catch (err) {
      setError(err.message || 'Authentication failed. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="auth-container">
      <div className="auth-card">
        {/* Brand Header */}
        <div className="auth-header">
          <div className="brand-badge">
            <CheckSquare size={28} className="brand-icon" />
          </div>
          <h1 className="brand-title">MeetFlow AI</h1>
          <p className="brand-subtitle">
            {isRegister
              ? 'Create an account to start extracting and clarifying meeting action items with MeetFlow AI'
              : 'Sign in to access your meeting transcripts and action items'}
          </p>
        </div>

        {/* Error Banner */}
        {error && (
          <div className="error-alert" role="alert" aria-live="assertive">
            <AlertCircle size={18} className="error-icon" />
            <span className="error-text">{error}</span>
          </div>
        )}

        {/* Auth Form */}
        <form onSubmit={handleSubmit} className="auth-form" noValidate>
          <div className="form-group">
            <label htmlFor="auth-email" className="form-label">
              Email Address
            </label>
            <div className="input-wrapper">
              <Mail size={18} className="input-icon" />
              <input
                id="auth-email"
                type="email"
                name="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="name@company.com"
                className="form-input"
                disabled={isSubmitting}
                aria-label="Email address"
              />
            </div>
          </div>

          <div className="form-group">
            <label htmlFor="auth-password" className="form-label">
              Password
            </label>
            <div className="input-wrapper">
              <Lock size={18} className="input-icon" />
              <input
                id="auth-password"
                type="password"
                name="password"
                autoComplete={isRegister ? 'new-password' : 'current-password'}
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="form-input"
                disabled={isSubmitting}
                aria-label="Password"
              />
            </div>
          </div>

          {isRegister && (
            <div className="form-group">
              <label htmlFor="auth-confirm-password" className="form-label">
                Confirm Password
              </label>
              <div className="input-wrapper">
                <ShieldCheck size={18} className="input-icon" />
                <input
                  id="auth-confirm-password"
                  type="password"
                  name="confirmPassword"
                  autoComplete="new-password"
                  required
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="••••••••"
                  className="form-input"
                  disabled={isSubmitting}
                  aria-label="Confirm password"
                />
              </div>
            </div>
          )}

          <button
            type="submit"
            className="btn btn-primary btn-block"
            disabled={isSubmitting}
            aria-label={isRegister ? 'Create Account' : 'Sign In'}
          >
            {isSubmitting ? (
              <span className="btn-loading">
                <span className="spinner-sm"></span>
                <span>{isRegister ? 'Creating Account...' : 'Signing In...'}</span>
              </span>
            ) : (
              <span className="btn-content">
                <span>{isRegister ? 'Register Account' : 'Sign In'}</span>
                <ArrowRight size={18} />
              </span>
            )}
          </button>
        </form>

        {/* Footer Toggle */}
        <div className="auth-footer">
          {isRegister ? (
            <p className="footer-text">
              Already have an account?{' '}
              <Link to="/login" className="auth-link">
                Sign In
              </Link>
            </p>
          ) : (
            <p className="footer-text">
              Don't have an account?{' '}
              <Link to="/register" className="auth-link">
                Create Account
              </Link>
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
