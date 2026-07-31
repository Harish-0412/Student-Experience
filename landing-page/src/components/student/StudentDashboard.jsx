import React from 'react';
import { useApp } from '../../context/AppContext';
import {
  AlertTriangle,
  ArrowRight,
  Brain,
  Check,
  Play,
  Target,
  TrendingUp,
  Zap,
} from 'lucide-react';

export const StudentDashboard = () => {
  const {
    studentProfile,
    selectedGoal,
    plan,
    progress,
    masteryData,
    evidence,
    risks,
    tasks,
    toggleTaskCompletion,
    setStudentTab,
    selectFocusTask,
    requestReplan,
  } = useApp();

  if (!selectedGoal) {
    return (
      <EmptyState
        title={`Welcome, ${studentProfile?.display_name || 'student'}`}
        body="Create your first goal to run clarification, feasibility, skill-gap, and planning services."
        action={() => setStudentTab('goals')}
      />
    );
  }

  const pendingTasks = tasks
    .filter((task) => task.status !== 'completed')
    .slice(0, 3);
  const openRisk = risks.find((risk) => risk.status === 'open');
  const confidence = progress
    ? Math.round(progress.goal_confidence)
    : null;
  const mastered = masteryData.filter((item) => item.score >= 0.8).length;

  return (
    <div className="mx-auto max-w-7xl space-y-8 pb-12">
      <section className="border-b border-white/10 pb-7">
        <div className="flex flex-col justify-between gap-5 lg:flex-row lg:items-end">
          <div>
            <p className="mb-2 text-xs font-semibold uppercase text-purple-300">
              {plan ? `Plan v${plan.version} · ${plan.status}` : 'Planning required'}
            </p>
            <h1 className="text-3xl font-extrabold text-white">
              {studentProfile?.display_name}
            </h1>
            <p className="mt-2 max-w-2xl text-sm text-gray-400">
              Active goal: <strong className="text-white">{selectedGoal.title}</strong>
              {selectedGoal.target_date && ` · target ${selectedGoal.target_date}`}
            </p>
          </div>
          <div className="flex items-center gap-3">
            <div className="text-right">
              <div className="text-xs text-gray-500">Goal confidence</div>
              <div className="text-2xl font-bold text-white">
                {confidence === null ? 'Not calculated' : `${confidence}%`}
              </div>
            </div>
            <TrendingUp className="h-7 w-7 text-emerald-400" />
          </div>
        </div>
      </section>

      {openRisk && (
        <section className="flex flex-col justify-between gap-4 rounded-lg border border-amber-500/25 bg-amber-500/10 p-4 sm:flex-row sm:items-center">
          <div className="flex items-start gap-3">
            <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-amber-400" />
            <div>
              <div className="text-sm font-bold capitalize text-amber-200">
                {openRisk.risk_type.replaceAll('_', ' ')} · {openRisk.severity}
              </div>
              <p className="mt-1 text-xs text-amber-100/75">
                {openRisk.intervention}
              </p>
            </div>
          </div>
          {plan?.status === 'approved' && (
            <button
              type="button"
              onClick={() => requestReplan(openRisk)}
              className="shrink-0 rounded-lg border border-amber-500/30 px-4 py-2 text-xs font-bold text-amber-200 hover:bg-amber-500/10"
            >
              Request adaptive replan
            </button>
          )}
        </section>
      )}

      <div className="grid gap-8 lg:grid-cols-[minmax(0,2fr)_minmax(260px,1fr)]">
        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="flex items-center gap-2 text-lg font-bold text-white">
              <Target className="h-5 w-5 text-purple-400" />
              Current actions
            </h2>
            <button
              type="button"
              onClick={() => setStudentTab('today')}
              className="text-xs font-semibold text-purple-300"
            >
              Open planner
            </button>
          </div>

          {pendingTasks.length ? (
            <div className="divide-y divide-white/10 border-y border-white/10">
              {pendingTasks.map((task) => (
                <div
                  key={task.id}
                  className="flex flex-col justify-between gap-4 py-5 sm:flex-row sm:items-center"
                >
                  <div className="flex items-start gap-3">
                    <button
                      type="button"
                      onClick={() => toggleTaskCompletion(task.id)}
                      className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-md border border-white/20 hover:border-purple-400"
                      title="Mark task complete"
                    >
                      <Check className="h-3.5 w-3.5 text-transparent" />
                    </button>
                    <div>
                      <div className="text-xs font-semibold text-purple-300">
                        {task.category} · {task.estimatedMinutes} min
                      </div>
                      <h3 className="mt-1 text-sm font-bold text-white">
                        {task.title}
                      </h3>
                      <p className="mt-1 text-xs text-gray-500">
                        {task.explanation}
                      </p>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => selectFocusTask(task)}
                    className="flex shrink-0 items-center justify-center gap-2 rounded-lg bg-purple-600 px-4 py-2 text-xs font-bold text-white hover:bg-purple-500"
                  >
                    <Play className="h-3.5 w-3.5 fill-current" /> Focus
                  </button>
                </div>
              ))}
            </div>
          ) : (
            <p className="border-y border-white/10 py-8 text-sm text-gray-500">
              {plan?.status === 'proposed'
                ? 'Approve the proposed plan to begin task execution.'
                : 'No actionable tasks are available for this goal.'}
            </p>
          )}
        </section>

        <aside className="space-y-4">
          <button
            type="button"
            onClick={() =>
              pendingTasks[0]
                ? selectFocusTask(pendingTasks[0])
                : setStudentTab('focus')
            }
            className="w-full rounded-lg border border-white/10 bg-white/5 p-5 text-left hover:border-purple-500/40"
          >
            <div className="flex items-center gap-2 text-sm font-bold text-white">
              <Zap className="h-4 w-4 text-amber-400" />
              Focus session
            </div>
            <p className="mt-2 text-xs leading-relaxed text-gray-400">
              Record actual study time and reflection against your active goal.
            </p>
            <ArrowRight className="mt-4 h-4 w-4 text-purple-300" />
          </button>
          <button
            type="button"
            onClick={() => setStudentTab('tutor')}
            className="w-full rounded-lg border border-white/10 bg-white/5 p-5 text-left hover:border-purple-500/40"
          >
            <div className="flex items-center gap-2 text-sm font-bold text-white">
              <Brain className="h-4 w-4 text-purple-400" />
              Contextual tutor
            </div>
            <p className="mt-2 text-xs leading-relaxed text-gray-400">
              Ask for an explanation, hint, quiz, or debugging help within this
              goal.
            </p>
          </button>
        </aside>
      </div>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <Stat label="Mastered competencies" value={`${mastered} / ${masteryData.length}`} />
        <Stat label="Focus minutes" value={progress?.focus_minutes ?? 0} />
        <Stat label="Verified evidence" value={progress?.verified_evidence_count ?? 0} />
        <Stat label="Evidence submissions" value={evidence.length} />
      </div>
    </div>
  );
};

const EmptyState = ({ title, body, action }) => (
  <div className="mx-auto max-w-3xl py-20">
    <Target className="mb-5 h-9 w-9 text-purple-400" />
    <h1 className="text-3xl font-extrabold text-white">{title}</h1>
    <p className="mt-3 max-w-xl text-sm text-gray-400">{body}</p>
    <button
      type="button"
      onClick={action}
      className="mt-6 rounded-lg bg-purple-600 px-5 py-3 text-sm font-bold text-white"
    >
      Create a goal
    </button>
  </div>
);

const Stat = ({ label, value }) => (
  <div className="border-t border-white/10 pt-4">
    <div className="text-xs text-gray-500">{label}</div>
    <div className="mt-1 text-2xl font-bold text-white">{value}</div>
  </div>
);
