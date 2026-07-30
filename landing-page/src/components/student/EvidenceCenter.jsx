import React, { useState } from 'react';
import { useApp } from '../../context/AppContext';
import {
  CheckCircle2,
  Clock,
  FileText,
  ShieldCheck,
  UploadCloud,
  X,
  XCircle,
} from 'lucide-react';

const sha256 = async (value) => {
  const bytes = new TextEncoder().encode(value);
  const digest = await crypto.subtle.digest('SHA-256', bytes);
  return [...new Uint8Array(digest)]
    .map((byte) => byte.toString(16).padStart(2, '0'))
    .join('');
};

export const EvidenceCenter = () => {
  const {
    selectedGoal,
    goalGraph,
    evidence,
    addEvidence,
  } = useApp();
  const [showUpload, setShowUpload] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [report, setReport] = useState(null);

  const submit = async (event) => {
    event.preventDefault();
    setSubmitting(true);
    const data = new FormData(event.currentTarget);
    const title = data.get('title').trim();
    const content = data.get('content').trim();
    const serialized = `${title}\n${content}`;
    const bytes = new TextEncoder().encode(serialized);
    try {
      const result = await addEvidence({
        goal_id: selectedGoal.id,
        competency_ref: data.get('competency_ref').trim(),
        original_name: `${title}.txt`,
        media_type: content.startsWith('http')
          ? 'text/uri-list'
          : 'text/plain',
        size_bytes: bytes.length,
        sha256: await sha256(serialized),
        storage_key: `student-submissions/${crypto.randomUUID()}.txt`,
        content_text: content,
        acceptance_criteria: [data.get('acceptance_criterion').trim()],
        idempotency_key: crypto.randomUUID(),
      });
      setReport(result);
      setShowUpload(false);
    } finally {
      setSubmitting(false);
    }
  };

  if (!selectedGoal) {
    return (
      <div className="mx-auto max-w-3xl py-20 text-center text-sm text-gray-500">
        Select a goal before submitting evidence.
      </div>
    );
  }

  const competencyOptions = [
    ...new Set(
      (goalGraph?.nodes || [])
        .map((node) => node.title)
        .filter(Boolean),
    ),
  ];

  return (
    <div className="mx-auto max-w-7xl space-y-8 pb-12">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <h1 className="flex items-center gap-3 text-3xl font-extrabold text-white">
            <ShieldCheck className="h-8 w-8 text-purple-400" />
            Evidence Center
          </h1>
          <p className="mt-2 text-sm text-gray-400">{selectedGoal.title}</p>
        </div>
        <button
          type="button"
          onClick={() => setShowUpload(true)}
          className="flex items-center justify-center gap-2 rounded-lg bg-purple-600 px-5 py-3 text-sm font-bold text-white hover:bg-purple-500"
        >
          <UploadCloud className="h-4 w-4" /> Submit evidence
        </button>
      </div>

      {evidence.length ? (
        <div className="divide-y divide-white/10 border-y border-white/10">
          {evidence.map((item) => (
            <div
              key={item.id}
              className="grid gap-4 py-5 md:grid-cols-[44px_minmax(0,1fr)_180px]"
            >
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-purple-500/15 text-purple-300">
                <FileText className="h-5 w-5" />
              </div>
              <div>
                <div className="text-sm font-bold text-white">
                  {item.original_name}
                </div>
                <div className="mt-1 text-xs text-gray-500">
                  {item.competency_ref} · {item.media_type} · {item.size_bytes}{' '}
                  bytes
                </div>
                <div className="mt-2 font-mono text-[10px] text-gray-600">
                  SHA-256 {item.sha256}
                </div>
              </div>
              <div>
                <Status status={item.status} />
                <div className="mt-2 text-xs text-gray-500">
                  {new Date(item.submitted_at).toLocaleString()}
                </div>
                {item.quality_score !== null && (
                  <div className="mt-1 text-xs text-purple-300">
                    Quality {Math.round(item.quality_score * 100)}%
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="border-y border-white/10 py-14 text-center text-sm text-gray-500">
          No evidence has been submitted for this goal.
        </div>
      )}

      {report && (
        <div className="rounded-lg border border-purple-500/25 bg-purple-500/10 p-4 text-xs text-purple-100">
          <div className="font-bold capitalize">
            Verification decision: {report.decision.replaceAll('_', ' ')}
          </div>
          <p className="mt-1 text-purple-100/70">{report.feedback}</p>
          {report.integrity_flags.length > 0 && (
            <p className="mt-2 text-amber-300">
              Integrity flags: {report.integrity_flags.join(', ')}
            </p>
          )}
        </div>
      )}

      {showUpload && (
        <div className="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto bg-black/85 p-4 backdrop-blur-md">
          <form
            onSubmit={submit}
            className="w-full max-w-lg space-y-5 rounded-2xl border border-white/15 bg-[#111116] p-7"
          >
            <div className="flex items-start justify-between">
              <div>
                <p className="text-xs font-semibold uppercase text-purple-300">
                  {selectedGoal.title}
                </p>
                <h2 className="mt-1 text-2xl font-bold text-white">
                  Submit evidence
                </h2>
              </div>
              <button
                type="button"
                onClick={() => setShowUpload(false)}
                className="rounded-lg p-2 text-gray-400 hover:bg-white/10"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <Field label="Evidence title" name="title" required />
            <label className="block text-xs font-medium text-gray-300">
              Competency reference
              <input
                name="competency_ref"
                list="competency-options"
                required
                className="mt-1.5 w-full rounded-lg border border-white/10 bg-black/40 p-3 text-sm text-white outline-none focus:border-purple-500"
              />
              <datalist id="competency-options">
                {competencyOptions.map((option) => (
                  <option key={option} value={option} />
                ))}
              </datalist>
            </label>
            <label className="block text-xs font-medium text-gray-300">
              Artifact text or public URL
              <textarea
                name="content"
                required
                minLength={3}
                rows={5}
                className="mt-1.5 w-full rounded-lg border border-white/10 bg-black/40 p-3 text-sm text-white outline-none focus:border-purple-500"
              />
            </label>
            <Field
              label="Acceptance criterion"
              name="acceptance_criterion"
              required
            />
            <button
              type="submit"
              disabled={submitting}
              className="w-full rounded-lg bg-purple-600 py-3 text-sm font-bold text-white disabled:opacity-50"
            >
              {submitting ? 'Verifying...' : 'Submit for verification'}
            </button>
          </form>
        </div>
      )}
    </div>
  );
};

const Field = ({ label, ...props }) => (
  <label className="block text-xs font-medium text-gray-300">
    {label}
    <input
      {...props}
      className="mt-1.5 w-full rounded-lg border border-white/10 bg-black/40 p-3 text-sm text-white outline-none focus:border-purple-500"
    />
  </label>
);

const Status = ({ status }) => {
  const verified = status === 'verified';
  const rejected = status === 'rejected';
  const Icon = verified ? CheckCircle2 : rejected ? XCircle : Clock;
  return (
    <span
      className={`inline-flex items-center gap-1.5 text-xs font-bold capitalize ${
        verified
          ? 'text-emerald-300'
          : rejected
            ? 'text-rose-300'
            : 'text-amber-300'
      }`}
    >
      <Icon className="h-3.5 w-3.5" />
      {status.replaceAll('_', ' ')}
    </span>
  );
};
