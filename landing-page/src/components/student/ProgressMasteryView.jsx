import React from 'react';
import { useApp } from '../../context/AppContext';
import {
  AlertTriangle,
  RefreshCw,
  ShieldCheck,
  TrendingUp,
} from 'lucide-react';

const percent = (value) => `${Math.round((value || 0) * 100)}%`;

export const ProgressMasteryView = () => {
  const {
    selectedGoal,
    progress,
    masteryData,
    risks,
    scanRisks,
    busy,
  } = useApp();

  if (!selectedGoal) {
    return (
      <div className="mx-auto max-w-3xl py-20 text-center text-sm text-gray-500">
        Select a goal to view progress and mastery.
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-7xl space-y-8 pb-12">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <h1 className="flex items-center gap-3 text-3xl font-extrabold text-white">
            <TrendingUp className="h-8 w-8 text-purple-400" />
            Progress & Mastery
          </h1>
          <p className="mt-2 text-sm text-gray-400">{selectedGoal.title}</p>
        </div>
        <button
          type="button"
          disabled={busy}
          onClick={scanRisks}
          className="flex items-center justify-center gap-2 rounded-lg border border-white/15 px-4 py-2.5 text-xs font-bold text-gray-200 hover:bg-white/5 disabled:opacity-50"
        >
          <RefreshCw className="h-4 w-4" /> Scan current risks
        </button>
      </div>

      {progress && (
        <div className="grid grid-cols-2 gap-4 border-y border-white/10 py-6 md:grid-cols-4">
          <Metric label="Activity" value={percent(progress.activity_progress)} />
          <Metric label="Milestones" value={percent(progress.milestone_progress)} />
          <Metric label="Mastery" value={percent(progress.mastery_progress)} />
          <Metric label="Goal confidence" value={percent(progress.goal_confidence)} />
          <Metric label="Focus minutes" value={progress.focus_minutes} />
          <Metric label="Assessments" value={progress.assessment_count} />
          <Metric label="Verified evidence" value={progress.verified_evidence_count} />
          <Metric
            label="Schedule variance"
            value={percent(progress.schedule_variance)}
          />
        </div>
      )}

      <section className="space-y-4">
        <h2 className="flex items-center gap-2 text-lg font-bold text-white">
          <ShieldCheck className="h-5 w-5 text-emerald-400" />
          Mastery estimates
        </h2>
        {masteryData.length ? (
          <div className="overflow-x-auto border-y border-white/10">
            <table className="w-full min-w-[780px] text-left text-sm text-gray-300">
              <thead className="border-b border-white/10 text-xs uppercase text-gray-500">
                <tr>
                  <th className="p-4">Competency</th>
                  <th className="p-4">Estimate</th>
                  <th className="p-4">Confidence interval</th>
                  <th className="p-4">Evidence</th>
                  <th className="p-4">Next assessment</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/10">
                {masteryData.map((mastery) => (
                  <tr key={mastery.id}>
                    <td className="p-4 font-bold text-white">
                      {mastery.competency_ref}
                    </td>
                    <td className="p-4">
                      <div className="flex items-center gap-3">
                        <span className="w-12 font-bold text-purple-300">
                          {percent(mastery.score)}
                        </span>
                        <div className="h-1.5 w-24 overflow-hidden rounded-full bg-white/10">
                          <div
                            className="h-full bg-purple-500"
                            style={{ width: percent(mastery.score) }}
                          />
                        </div>
                      </div>
                    </td>
                    <td className="p-4 text-xs">
                      {percent(mastery.confidence_lower)} –{' '}
                      {percent(mastery.confidence_upper)}
                    </td>
                    <td className="p-4">{mastery.evidence_count}</td>
                    <td className="p-4 text-xs text-gray-400">
                      {mastery.next_assessment_recommendation}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="border-y border-white/10 py-10 text-sm text-gray-500">
            No mastery estimate exists yet. Complete assessments or submit
            verified evidence to produce one.
          </p>
        )}
      </section>

      <section className="space-y-4">
        <h2 className="flex items-center gap-2 text-lg font-bold text-white">
          <AlertTriangle className="h-5 w-5 text-amber-400" />
          Detected risks
        </h2>
        {risks.length ? (
          <div className="divide-y divide-white/10 border-y border-white/10">
            {risks.map((risk) => (
              <div
                key={risk.id}
                className="grid gap-3 py-4 md:grid-cols-[180px_minmax(0,1fr)_110px]"
              >
                <div>
                  <div className="text-xs font-bold capitalize text-amber-300">
                    {risk.risk_type.replaceAll('_', ' ')}
                  </div>
                  <div className="mt-1 text-[10px] uppercase text-gray-500">
                    {risk.severity}
                  </div>
                </div>
                <p className="text-xs text-gray-300">{risk.intervention}</p>
                <div className="text-xs capitalize text-gray-500">
                  {risk.status}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="border-y border-white/10 py-8 text-sm text-gray-500">
            No risk scan findings are stored for this goal.
          </p>
        )}
      </section>
    </div>
  );
};

const Metric = ({ label, value }) => (
  <div>
    <div className="text-xs text-gray-500">{label}</div>
    <div className="mt-1 text-xl font-bold text-white">{value}</div>
  </div>
);
