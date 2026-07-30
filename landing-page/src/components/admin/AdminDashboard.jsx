import React from 'react';
import { useApp } from '../../context/AppContext';
import {
  Activity,
  CheckCircle2,
  Cpu,
  ShieldAlert,
  Users,
} from 'lucide-react';

export const AdminDashboard = () => {
  const {
    students,
    agents,
    agentRuns,
    reviewItems,
    systemHealth,
    operationsStatus,
    securityPolicy,
    verifyAudit,
    setAdminTab,
  } = useApp();
  const failedRuns = agentRuns.filter((run) => run.status === 'failed').length;
  const completedRuns = agentRuns.filter((run) =>
    ['completed', 'student_approval_required', 'admin_review_required'].includes(
      run.status,
    ),
  ).length;

  return (
    <div className="mx-auto max-w-7xl space-y-8 pb-12">
      <div>
        <p className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase text-emerald-300">
          <CheckCircle2 className="h-4 w-4" />
          {operationsStatus?.status || systemHealth?.status || 'Health unavailable'}
        </p>
        <h1 className="text-3xl font-extrabold text-white">
          Admin Operations & Governance
        </h1>
        <p className="mt-2 text-sm text-gray-400">
          {operationsStatus
            ? `Operational phases ${operationsStatus.phases.join(', ')} · audit ${operationsStatus.audit.valid ? 'verified' : 'degraded'}`
            : systemHealth
            ? `${systemHealth.service} · version ${systemHealth.version}`
            : 'Backend health has not been loaded.'}
        </p>
      </div>

      <div className="grid grid-cols-2 gap-4 border-y border-white/10 py-6 md:grid-cols-4">
        <Metric icon={Users} label="Students" value={students.length} />
        <Metric icon={Cpu} label="Registered agents" value={agents.length} />
        <Metric icon={ShieldAlert} label="Pending reviews" value={reviewItems.length} />
        <Metric icon={Activity} label="Failed agent runs" value={failedRuns} />
      </div>

      <div className="grid gap-10 lg:grid-cols-2">
        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold text-white">Review queue</h2>
            <button
              type="button"
              onClick={() => setAdminTab('reviews')}
              className="text-xs font-bold text-purple-300"
            >
              Open queue
            </button>
          </div>
          {reviewItems.length ? (
            <div className="divide-y divide-white/10 border-y border-white/10">
              {reviewItems.slice(0, 5).map((item) => (
                <div key={item.id} className="py-4">
                  <div className="text-xs font-bold text-amber-300">
                    Evidence verification
                  </div>
                  <div className="mt-1 text-sm font-bold text-white">
                    {item.original_name}
                  </div>
                  <div className="mt-1 text-xs text-gray-500">
                    Student {item.student_id} · goal {item.goal_id}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="border-y border-white/10 py-8 text-sm text-gray-500">
              The review queue is clear.
            </p>
          )}
        </section>

        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold text-white">Agent execution</h2>
            <button
              type="button"
              onClick={() => setAdminTab('agents')}
              className="text-xs font-bold text-purple-300"
            >
              Open registry
            </button>
          </div>
          <div className="grid grid-cols-2 gap-4 border-y border-white/10 py-5">
            <Metric label="Persisted runs" value={agentRuns.length} />
            <Metric label="Completed or routed" value={completedRuns} />
          </div>
          <div className="divide-y divide-white/10">
            {agents.slice(0, 6).map((agent) => (
              <div
                key={`${agent.phase}-${agent.name}`}
                className="flex items-center justify-between gap-4 py-3"
              >
                <div>
                  <div className="text-xs font-bold text-white">{agent.name}</div>
                  <div className="mt-1 text-[10px] text-gray-500">
                    {agent.phase} · v{agent.version}
                  </div>
                </div>
                <span className="text-[10px] uppercase text-purple-300">
                  {agent.lastStatus.replaceAll('_', ' ')}
                </span>
              </div>
            ))}
          </div>
        </section>
      </div>

      {operationsStatus && (
        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold text-white">Operational readiness</h2>
            <button
              type="button"
              onClick={verifyAudit}
              className="text-xs font-bold text-purple-300"
            >
              Verify audit chain
            </button>
          </div>
          <div className="divide-y divide-white/10 border-y border-white/10">
            {operationsStatus.components.map((component) => (
              <div
                key={component.name}
                className="grid gap-2 py-3 text-xs sm:grid-cols-[220px_90px_minmax(0,1fr)]"
              >
                <span className="font-bold text-white">
                  {component.name.replaceAll('_', ' ')}
                </span>
                <span
                  className={
                    component.status === 'ready'
                      ? 'text-emerald-300'
                      : 'text-amber-300'
                  }
                >
                  {component.status}
                </span>
                <span className="text-gray-500">{component.detail}</span>
              </div>
            ))}
          </div>
          <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
            <Metric label="Requests" value={operationsStatus.metrics.requests_total} />
            <Metric label="P95 latency" value={`${operationsStatus.metrics.latency_p95_ms} ms`} />
            <Metric label="Rate limited" value={operationsStatus.metrics.rate_limited_total} />
            <Metric
              label="Max inflight"
              value={securityPolicy?.max_inflight_requests ?? '—'}
            />
          </div>
        </section>
      )}
    </div>
  );
};

const Metric = ({ icon: Icon, label, value }) => (
  <div>
    <div className="flex items-center gap-2 text-xs text-gray-500">
      {Icon && <Icon className="h-3.5 w-3.5" />}
      {label}
    </div>
    <div className="mt-2 text-2xl font-bold text-white">{value}</div>
  </div>
);
