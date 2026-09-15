import React, { useState, useEffect } from 'react';
import { actionItemsApi } from '../api/client';
import { X, GitMerge, AlertCircle, CheckCircle2, ArrowRight } from 'lucide-react';

export function DuplicateMergeModal({ isOpen, primaryItem, onClose, onMerged }) {
  const [candidates, setCandidates] = useState([]);
  const [loading, setLoading] = useState(false);
  const [merging, setMerging] = useState(false);
  const [error, setError] = useState('');
  const [selectedDuplicateId, setSelectedDuplicateId] = useState(null);

  useEffect(() => {
    if (isOpen && primaryItem) {
      fetchCandidates();
    }
  }, [isOpen, primaryItem]);

  const fetchCandidates = async () => {
    setLoading(true);
    setError('');
    try {
      const data = await actionItemsApi.getDuplicates(primaryItem.id);
      setCandidates(data);
      if (data.length > 0) {
        setSelectedDuplicateId(data[0].id);
      }
    } catch (err) {
      setError(err.message || 'Failed to fetch duplicate candidates.');
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen || !primaryItem) return null;

  const handleMerge = async () => {
    if (!selectedDuplicateId) return;

    setMerging(true);
    setError('');
    try {
      const mergedItem = await actionItemsApi.merge(primaryItem.id, selectedDuplicateId);
      if (onMerged) {
        onMerged(mergedItem);
      }
      onClose();
    } catch (err) {
      setError(err.message || 'Failed to merge duplicate action items.');
    } finally {
      setMerging(false);
    }
  };

  const selectedCandidate = candidates.find((c) => c.id === selectedDuplicateId);

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-container modal-lg" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-title-group">
            <GitMerge size={20} className="modal-merge-icon" />
            <h2 className="modal-title">Merge Duplicate Action Items</h2>
          </div>
          <button onClick={onClose} className="modal-close-btn" aria-label="Close modal">
            <X size={18} />
          </button>
        </div>

        <div className="modal-body">
          {error && (
            <div className="error-alert">
              <AlertCircle size={18} className="error-icon" />
              <span>{error}</span>
            </div>
          )}

          {/* Primary Item Preview */}
          <div className="merge-primary-card">
            <span className="merge-badge primary">Primary Item #{primaryItem.id} (Retained)</span>
            <h4 className="merge-task-title">{primaryItem.task}</h4>
            <div className="merge-meta-row">
              <span>Owner: <strong>{primaryItem.owner || 'Unassigned'}</strong></span>
              <span>Deadline: <strong>{primaryItem.deadline || 'None'}</strong></span>
              <span>Mentions: <strong>{primaryItem.mention_count || 1}</strong></span>
            </div>
          </div>

          <div className="merge-divider">
            <ArrowRight size={20} />
          </div>

          {/* Candidate Selection */}
          <div className="merge-candidates-section">
            <h4 className="section-subtitle">
              Duplicate Candidates ({candidates.length})
            </h4>

            {loading ? (
              <div className="loading-state">
                <div className="spinner-sm" />
                <span>Searching for semantic & syntactic duplicate candidates...</span>
              </div>
            ) : candidates.length === 0 ? (
              <div className="empty-candidates">
                <CheckCircle2 size={24} color="var(--success)" />
                <p>No duplicate candidates found for this action item (similarity threshold &gt; 0.6).</p>
              </div>
            ) : (
              <div className="candidates-list">
                {candidates.map((cand) => (
                  <div
                    key={cand.id}
                    className={`candidate-card ${selectedDuplicateId === cand.id ? 'selected' : ''}`}
                    onClick={() => setSelectedDuplicateId(cand.id)}
                  >
                    <div className="candidate-header">
                      <div className="radio-selection">
                        <input
                          type="radio"
                          name="duplicateSelection"
                          checked={selectedDuplicateId === cand.id}
                          onChange={() => setSelectedDuplicateId(cand.id)}
                        />
                        <span className="candidate-id">Item #{cand.id}</span>
                      </div>
                      <span className="similarity-badge">
                        {Math.round(cand.similarity_score * 100)}% Match
                      </span>
                    </div>

                    <p className="candidate-task">{cand.task}</p>

                    <div className="candidate-meta">
                      <span>Owner: {cand.owner || 'None'}</span>
                      <span>Deadline: {cand.deadline || 'None'}</span>
                      <span>Meeting #{cand.meeting_id}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {selectedCandidate && (
            <div className="merge-info-note">
              <p>
                Merging will increment <strong>Item #{primaryItem.id}</strong>'s mention count, fill in any missing owner/deadline, and permanently delete <strong>Item #{selectedCandidate.id}</strong>.
              </p>
            </div>
          )}
        </div>

        <div className="modal-footer">
          <button type="button" onClick={onClose} className="btn btn-secondary" disabled={merging}>
            Cancel
          </button>
          <button
            type="button"
            onClick={handleMerge}
            className="btn btn-primary"
            disabled={merging || candidates.length === 0 || !selectedDuplicateId}
          >
            {merging ? 'Merging Items...' : `Merge into Item #${primaryItem.id}`}
          </button>
        </div>
      </div>
    </div>
  );
}
