import React, { useState } from 'react';
import { meetingsApi } from '../api/client';
import {
  X,
  FileText,
  Upload,
  Mic,
  Sparkles,
  CheckCircle,
  AlertCircle,
  Clock,
  MessageSquare,
  Smile,
  Frown,
  Meh
} from 'lucide-react';

const SAMPLE_TRANSCRIPT = `Priya: Okay so for the launch next week, I'll handle the press release, should be done by Thursday.
Sam: I can take the social media graphics, I'll have drafts by Wednesday.
Priya: Great. Someone needs to update the pricing page too, but I'm not sure who's free for that.
Rahul: I could maybe look at it if no one else can, but I have the client call all week.
Priya: Let's flag that one. Also we need the QA pass done before Friday's release.
Sam: I think that's on the QA team but honestly I don't know who exactly picks that up.
Priya: Okay, let's note that as unclear too. Last thing - can someone send the launch email to the mailing list?
Rahul: Yeah I'll do that, I'll send it Friday morning right before the release goes live.
Priya: Also, we've decided to push the enterprise pricing tier discussion to next quarter.
Sam: Agreed, and we're keeping the current logo for this launch instead of the redesign.`;

export function AddMeetingModal({ isOpen, onClose, onMeetingCreated }) {
  const [tab, setTab] = useState('paste'); // 'paste' | 'txt' | 'docx' | 'audio'
  const [title, setTitle] = useState('');
  const [meetingDate, setMeetingDate] = useState(() => new Date().toISOString().split('T')[0]);
  const [transcriptText, setTranscriptText] = useState('');
  const [selectedFile, setSelectedFile] = useState(null);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState(null);

  if (!isOpen) return null;

  const handleUseSample = () => {
    setTitle('Q3 Product Launch Sync');
    setTranscriptText(SAMPLE_TRANSCRIPT);
    setError('');
  };

  const handleFileChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      setSelectedFile(file);
      if (!title) {
        // Auto-generate title from filename
        const cleanName = file.name.replace(/\.[^/.]+$/, '').replace(/[-_]/g, ' ');
        setTitle(cleanName.charAt(0).toUpperCase() + cleanName.slice(1));
      }
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setResult(null);

    if (tab === 'paste' && !transcriptText.trim()) {
      setError('Please enter or paste meeting transcript text.');
      return;
    }

    if (tab !== 'paste' && !selectedFile) {
      setError('Please select a file to upload.');
      return;
    }

    setLoading(true);

    try {
      let response;
      if (tab === 'paste') {
        response = await meetingsApi.createJson({
          title: title.trim() || undefined,
          transcript_text: transcriptText.trim(),
          meeting_date: meetingDate,
        });
      } else {
        const formData = new FormData();
        formData.append('file', selectedFile);
        if (title.trim()) formData.append('title', title.trim());
        formData.append('meeting_date', meetingDate);
        response = await meetingsApi.createFormData(formData);
      }

      setResult(response);
      if (onMeetingCreated) {
        onMeetingCreated(response);
      }
    } catch (err) {
      setError(err.message || 'Failed to process meeting. Please check the backend connection.');
    } finally {
      setLoading(false);
    }
  };

  const handleReset = () => {
    setTitle('');
    setTranscriptText('');
    setSelectedFile(null);
    setError('');
    setResult(null);
    onClose();
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

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-container" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-title-group">
            <Sparkles size={20} className="modal-sparkle-icon" />
            <h2 className="modal-title">Ingest Meeting Transcript</h2>
          </div>
          <button onClick={onClose} className="modal-close-btn" aria-label="Close modal">
            <X size={18} />
          </button>
        </div>

        {result ? (
          <div className="modal-result-view">
            <div className="result-header">
              <div className="success-icon-badge">
                <CheckCircle size={32} />
              </div>
              <h3>Extraction & Ingestion Complete!</h3>
              <p>Meeting "{result.title}" has been successfully processed.</p>
            </div>

            <div className="result-stats-grid">
              <div className="result-stat-card">
                <span className="result-stat-label">Action Items</span>
                <span className="result-stat-value">{result.action_items?.length || 0}</span>
              </div>
              <div className="result-stat-card">
                <span className="result-stat-label">Clarifications</span>
                <span className="result-stat-value text-warning">
                  {result.action_items?.filter((i) => i.needs_clarification)?.length || 0}
                </span>
              </div>
              <div className="result-stat-card">
                <span className="result-stat-label">Decisions</span>
                <span className="result-stat-value">{result.decisions?.length || 0}</span>
              </div>
              <div className="result-stat-card">
                <span className="result-stat-label">Sentiment</span>
                <span className="result-stat-value sentiment-value">
                  {getSentimentIcon(result.sentiment)}
                  <span className="capitalize">{result.sentiment || 'Neutral'}</span>
                </span>
              </div>
            </div>

            <div className="modal-actions-bar">
              <button onClick={handleReset} className="btn btn-primary btn-block">
                View in Dashboard
              </button>
            </div>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="modal-form">
            {error && (
              <div className="error-alert">
                <AlertCircle size={18} className="error-icon" />
                <span>{error}</span>
              </div>
            )}

            {/* Ingestion Type Tabs */}
            <div className="ingestion-tabs">
              <button
                type="button"
                className={`tab-btn ${tab === 'paste' ? 'active' : ''}`}
                onClick={() => setTab('paste')}
              >
                <FileText size={16} />
                <span>Paste Text</span>
              </button>
              <button
                type="button"
                className={`tab-btn ${tab === 'txt' ? 'active' : ''}`}
                onClick={() => setTab('txt')}
              >
                <Upload size={16} />
                <span>.txt File</span>
              </button>
              <button
                type="button"
                className={`tab-btn ${tab === 'docx' ? 'active' : ''}`}
                onClick={() => setTab('docx')}
              >
                <FileText size={16} />
                <span>.docx File</span>
              </button>
              <button
                type="button"
                className={`tab-btn ${tab === 'audio' ? 'active' : ''}`}
                onClick={() => setTab('audio')}
              >
                <Mic size={16} />
                <span>Audio (Whisper)</span>
              </button>
            </div>

            {/* Metadata Fields */}
            <div className="form-row">
              <div className="form-group flex-1">
                <label className="form-label">Meeting Title (Optional)</label>
                <input
                  type="text"
                  placeholder="e.g. Q3 Launch Readiness Sync"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  className="form-input"
                  disabled={loading}
                />
              </div>

              <div className="form-group w-36">
                <label className="form-label">Meeting Date</label>
                <input
                  type="date"
                  value={meetingDate}
                  onChange={(e) => setMeetingDate(e.target.value)}
                  className="form-input"
                  disabled={loading}
                  required
                />
              </div>
            </div>

            {/* Tab Specific Content */}
            {tab === 'paste' ? (
              <div className="form-group">
                <div className="label-with-action">
                  <label className="form-label">Transcript Text</label>
                  <button
                    type="button"
                    onClick={handleUseSample}
                    className="btn-link-action"
                    disabled={loading}
                  >
                    <Sparkles size={14} />
                    <span>Try a sample transcript</span>
                  </button>
                </div>
                <textarea
                  rows={8}
                  placeholder="Speaker: I'll prepare the marketing deck by Friday..."
                  value={transcriptText}
                  onChange={(e) => setTranscriptText(e.target.value)}
                  className="form-textarea"
                  disabled={loading}
                />
              </div>
            ) : (
              <div className="form-group">
                <label className="form-label">
                  Upload{' '}
                  {tab === 'txt'
                    ? '.txt File'
                    : tab === 'docx'
                    ? '.docx Word Document'
                    : 'Audio Recording (.mp3, .wav, .m4a, .ogg, .flac)'}
                </label>
                <div className="file-dropzone">
                  <input
                    type="file"
                    id="file-upload-input"
                    accept={
                      tab === 'txt'
                        ? '.txt'
                        : tab === 'docx'
                        ? '.docx'
                        : '.mp3,.wav,.m4a,.ogg,.webm,.flac,.aac'
                    }
                    onChange={handleFileChange}
                    className="file-input-hidden"
                    disabled={loading}
                  />
                  <label htmlFor="file-upload-input" className="file-dropzone-label">
                    <Upload size={28} className="dropzone-icon" />
                    <span className="dropzone-title">
                      {selectedFile ? selectedFile.name : 'Click or browse to choose a file'}
                    </span>
                    <span className="dropzone-hint">
                      {selectedFile
                        ? `${(selectedFile.size / 1024).toFixed(1)} KB selected`
                        : tab === 'audio'
                        ? 'Audio will be automatically transcribed via Whisper AI'
                        : 'Plain text or Word document'}
                    </span>
                  </label>
                </div>
              </div>
            )}

            {/* Submit Actions */}
            <div className="modal-footer">
              <button
                type="button"
                onClick={onClose}
                className="btn btn-secondary"
                disabled={loading}
              >
                Cancel
              </button>
              <button
                type="submit"
                className="btn btn-primary"
                disabled={loading}
              >
                {loading ? (
                  <span className="btn-loading">
                    <span className="spinner-sm" />
                    <span>Extracting & Clarifying...</span>
                  </span>
                ) : (
                  <span className="btn-content">
                    <Sparkles size={16} />
                    <span>Process Transcript</span>
                  </span>
                )}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
