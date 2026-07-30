import React, { useState } from 'react';
import { useApp } from '../../context/AppContext';
import {
  CheckCircle2,
  ShieldAlert,
  XCircle,
} from 'lucide-react';

export const ReviewQueueView = () => {
  const { reviewItems, handleReviewAction } = useApp();
  const [selectedReview, setSelectedReview] = useState(null);
  const [reason, setReason] = useState('');
  const [deciding, setDeciding] = useState(false);

  const decide = async (decision) => {
    if (!selectedReview || reason.trim().length < 3) return;
    setDeciding(true);
    try {
      await handleReviewAction(selectedReview.id, decision, reason.trim());
      setSelectedReview(null);
      setReason('');
    } finally {
      setDeciding(false);
    }
  };

  return (
    <div className="mx-auto max-w-7xl space-y-8 pb-12">
      <div>
        <h1 className="flex items-center gap-3 text-3xl font-extrabold text-white">
          <ShieldAlert className="h-8 w-8 text-amber-400" />
          Evidence Review Queue
        </h1>
        <p className="mt-2 text-sm text-gray-400">
          {reviewItems.length} submission{reviewItems.length === 1 ? '' : 's'}{' '}
          awaiting an admin decision.
        </p>
      </div>

      <div className="grid gap-8 lg:grid-cols-[minmax(0,2fr)_minmax(280px,1fr)]">
        <div className="divide-y divide-white/10 border-y border-white/10">
          {reviewItems.map((item) => (
            <button
              type="button"
              key={item.id}
              onClick={() => {
                setSelectedReview(item);
                setReason('');
              }}
              className={`w-full py-5 text-left ${
                selectedReview?.id === item.id
                  ? 'bg-purple-500/10 px-4'
                  : 'hover:bg-white/[0.03]'
              }`}
            >
              <div className="flex items-center justify-between gap-4">
                <span className="text-xs font-bold text-amber-300">
                  {item.competency_ref}
                </span>
                <span className="text-[10px] text-gray-500">
                  {new Date(item.submitted_at).toLocaleString()}
                </span>
              </div>
              <h2 className="mt-2 text-sm font-bold text-white">
                {item.original_name}
              </h2>
              <p className="mt-1 text-xs text-gray-500">
                Student {item.student_id} · goal {item.goal_id}
              </p>
            </button>
          ))}
          {reviewItems.length === 0 && (
            <div className="py-14 text-center">
              <CheckCircle2 className="mx-auto h-9 w-9 text-emerald-400" />
              <h2 className="mt-3 text-base font-bold text-white">Queue clear</h2>
              <p className="mt-1 text-xs text-gray-500">
                No evidence requires human review.
              </p>
            </div>
          )}
        </div>

        <aside className="h-fit border-l border-white/10 pl-6">
          <h2 className="text-sm font-bold text-white">Decision</h2>
          {selectedReview ? (
            <div className="mt-5 space-y-5">
              <dl className="space-y-3 text-xs">
                <Row label="File" value={selectedReview.original_name} />
                <Row label="Media type" value={selectedReview.media_type} />
                <Row label="Size" value={`${selectedReview.size_bytes} bytes`} />
                <Row label="SHA-256" value={selectedReview.sha256} mono />
                <Row
                  label="Criteria"
                  value={selectedReview.acceptance_criteria.join(', ')}
                />
              </dl>
              <label className="block text-xs font-medium text-gray-300">
                Decision reason
                <textarea
                  value={reason}
                  onChange={(event) => setReason(event.target.value)}
                  rows={4}
                  minLength={3}
                  maxLength={2000}
                  className="mt-1.5 w-full rounded-lg border border-white/10 bg-black/40 p-3 text-sm text-white outline-none focus:border-purple-500"
                />
              </label>
              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  disabled={deciding || reason.trim().length < 3}
                  onClick={() => decide('approve')}
                  className="flex items-center justify-center gap-2 rounded-lg bg-emerald-500 py-2.5 text-xs font-bold text-black disabled:opacity-50"
                >
                  <CheckCircle2 className="h-4 w-4" /> Verify
                </button>
                <button
                  type="button"
                  disabled={deciding || reason.trim().length < 3}
                  onClick={() => decide('reject')}
                  className="flex items-center justify-center gap-2 rounded-lg border border-rose-500/30 py-2.5 text-xs font-bold text-rose-300 disabled:opacity-50"
                >
                  <XCircle className="h-4 w-4" /> Reject
                </button>
              </div>
            </div>
          ) : (
            <p className="mt-4 text-xs text-gray-500">
              Select a queue item to inspect its integrity metadata.
            </p>
          )}
        </aside>
      </div>
    </div>
  );
};

const Row = ({ label, value, mono = false }) => (
  <div>
    <dt className="text-gray-500">{label}</dt>
    <dd
      className={`mt-1 break-all text-gray-200 ${mono ? 'font-mono text-[10px]' : ''}`}
    >
      {value}
    </dd>
  </div>
);
