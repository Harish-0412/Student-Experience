import React, { useState } from 'react';
import { useApp } from '../../context/AppContext';
import {
  CheckCircle,
  Clock,
  GitBranch,
  Plus,
  Target,
  X,
} from 'lucide-react';

export const GoalsView = () => {
  const {
    goals,
    selectedGoal,
    selectedGoalId,
    setSelectedGoalId,
    goalGraph,
    plan,
    addGoal,
    decidePlan,
    busy,
  } = useApp();
  const [showWizard, setShowWizard] = useState(false);
  const [activeTab, setActiveTab] = useState('roadmap');

  const submitGoal = async (event) => {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    await addGoal({
      title: data.get('title'),
      raw_statement: data.get('raw_statement'),
      description: data.get('description'),
      category: data.get('category'),
      target_date: data.get('target_date'),
      priority: Number(data.get('priority')),
      success_criteria: data
        .get('success_criteria')
        .split('\n')
        .map((value) => value.trim())
        .filter(Boolean),
    });
    setShowWizard(false);
  };

  return (
    <div className="mx-auto max-w-7xl space-y-8 pb-12">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <h1 className="flex items-center gap-3 text-3xl font-extrabold text-white">
            <Target className="h-8 w-8 text-purple-400" />
            Goals & Roadmap
          </h1>
          <p className="mt-2 text-sm text-gray-400">
            {goals.length} goal{goals.length === 1 ? '' : 's'} in your account
          </p>
        </div>
        <button
          type="button"
          onClick={() => setShowWizard(true)}
          className="flex items-center justify-center gap-2 rounded-lg bg-purple-600 px-5 py-3 text-sm font-bold text-white hover:bg-purple-500"
        >
          <Plus className="h-4 w-4" /> Create goal
        </button>
      </div>

      {goals.length > 0 ? (
        <div className="grid gap-2 border-y border-white/10 py-3 md:grid-cols-2 xl:grid-cols-3">
          {goals.map((goal) => (
            <button
              type="button"
              key={goal.id}
              onClick={() => setSelectedGoalId(goal.id)}
              className={`p-4 text-left transition-colors ${
                goal.id === selectedGoalId
                  ? 'bg-purple-500/15'
                  : 'hover:bg-white/5'
              }`}
            >
              <div className="flex items-center justify-between gap-3">
                <span className="truncate text-sm font-bold text-white">
                  {goal.title}
                </span>
                <span className="text-[10px] uppercase text-purple-300">
                  {goal.status}
                </span>
              </div>
              <div className="mt-2 text-xs text-gray-500">
                {goal.target_date ? `Target ${goal.target_date}` : 'No target date'}
                {' · '}Priority {goal.priority}
              </div>
            </button>
          ))}
        </div>
      ) : (
        <div className="border-y border-white/10 py-14 text-center text-sm text-gray-500">
          No goals yet.
        </div>
      )}

      {selectedGoal && (
        <section className="space-y-6">
          <div className="flex flex-col justify-between gap-4 border-b border-white/10 pb-5 md:flex-row md:items-end">
            <div>
              <p className="text-xs font-semibold uppercase text-purple-300">
                {selectedGoal.category || 'Learning goal'}
              </p>
              <h2 className="mt-1 text-2xl font-bold text-white">
                {selectedGoal.title}
              </h2>
              <p className="mt-2 max-w-3xl text-sm text-gray-400">
                {selectedGoal.description || selectedGoal.raw_statement}
              </p>
            </div>
            {plan?.status === 'proposed' && (
              <div className="flex gap-2">
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => decidePlan('reject')}
                  className="rounded-lg border border-white/15 px-4 py-2 text-xs font-bold text-gray-300 hover:bg-white/5"
                >
                  Reject plan
                </button>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => decidePlan('approve')}
                  className="rounded-lg bg-emerald-500 px-4 py-2 text-xs font-bold text-black hover:bg-emerald-400"
                >
                  Approve plan v{plan.version}
                </button>
              </div>
            )}
          </div>

          <div className="flex gap-2">
            <Tab active={activeTab === 'roadmap'} onClick={() => setActiveTab('roadmap')}>
              Roadmap
            </Tab>
            <Tab active={activeTab === 'milestones'} onClick={() => setActiveTab('milestones')}>
              Milestones ({plan?.milestones?.length || 0})
            </Tab>
            <Tab active={activeTab === 'schedule'} onClick={() => setActiveTab('schedule')}>
              Schedule
            </Tab>
          </div>

          {activeTab === 'roadmap' && (
            <div className="space-y-3">
              {goalGraph?.nodes?.length ? (
                goalGraph.nodes.map((node) => {
                  const mastered =
                    node.required_level !== null &&
                    node.current_level !== null &&
                    node.current_level >= node.required_level;
                  return (
                    <div
                      key={node.id}
                      className="grid gap-3 border-b border-white/10 py-4 md:grid-cols-[80px_minmax(0,1fr)_180px]"
                    >
                      <div className="text-xs font-bold text-purple-300">
                        Step {node.sequence_order}
                      </div>
                      <div>
                        <div className="text-sm font-bold text-white">
                          {node.title}
                        </div>
                        <div className="mt-1 text-xs text-gray-500">
                          {node.estimated_hours} estimated hours
                          {node.is_optional ? ' · optional' : ''}
                        </div>
                      </div>
                      <div className="flex items-center gap-2 text-xs text-gray-400">
                        {mastered ? (
                          <CheckCircle className="h-4 w-4 text-emerald-400" />
                        ) : (
                          <GitBranch className="h-4 w-4 text-purple-400" />
                        )}
                        {node.current_level ?? 0} / {node.required_level ?? '—'} level
                      </div>
                    </div>
                  );
                })
              ) : (
                <EmptyRow text="The competency graph is not available for this goal." />
              )}
            </div>
          )}

          {activeTab === 'milestones' && (
            <div className="space-y-1">
              {plan?.milestones?.length ? (
                plan.milestones.map((milestone) => (
                  <div
                    key={milestone.id}
                    className="grid gap-4 border-b border-white/10 py-5 md:grid-cols-[44px_minmax(0,1fr)_130px]"
                  >
                    <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-purple-500/15 text-purple-300">
                      {milestone.status === 'completed' ? (
                        <CheckCircle className="h-4 w-4" />
                      ) : (
                        <Clock className="h-4 w-4" />
                      )}
                    </div>
                    <div>
                      <h3 className="text-sm font-bold text-white">
                        {milestone.title}
                      </h3>
                      <p className="mt-1 text-xs text-gray-500">
                        {milestone.description}
                      </p>
                      {milestone.acceptance_criteria.length > 0 && (
                        <ul className="mt-3 space-y-1 text-xs text-gray-400">
                          {milestone.acceptance_criteria.map((criterion) => (
                            <li key={criterion}>{criterion}</li>
                          ))}
                        </ul>
                      )}
                    </div>
                    <div className="text-xs text-gray-400">
                      {milestone.target_date}
                      <div className="mt-1 capitalize text-purple-300">
                        {milestone.status}
                      </div>
                    </div>
                  </div>
                ))
              ) : (
                <EmptyRow text="Generate a plan to see milestones." />
              )}
            </div>
          )}

          {activeTab === 'schedule' && (
            <div>
              {plan?.schedule ? (
                <>
                  <div className="grid grid-cols-2 gap-4 border-b border-white/10 pb-5 md:grid-cols-4">
                    <Metric label="Status" value={plan.schedule.status} />
                    <Metric label="Weekly capacity" value={`${plan.schedule.weekly_capacity_minutes} min`} />
                    <Metric label="Allocated" value={`${plan.schedule.allocated_minutes} min`} />
                    <Metric label="Health" value={`${Math.round(plan.schedule.schedule_health_score * 100)}%`} />
                  </div>
                  <div className="divide-y divide-white/10">
                    {plan.schedule.blocks.map((block) => {
                      const task = plan.tasks.find((item) => item.id === block.task_id);
                      return (
                        <div
                          key={block.id}
                          className="grid gap-2 py-4 text-xs md:grid-cols-[minmax(0,1fr)_220px_100px]"
                        >
                          <span className="font-bold text-white">
                            {task?.title || block.task_id}
                          </span>
                          <span className="text-gray-400">
                            {new Date(block.starts_at).toLocaleString()}
                          </span>
                          <span className="capitalize text-purple-300">
                            {block.status}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </>
              ) : (
                <EmptyRow text="No schedule has been generated." />
              )}
            </div>
          )}
        </section>
      )}

      {showWizard && (
        <div className="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto bg-black/85 p-4 backdrop-blur-md">
          <div className="w-full max-w-xl rounded-2xl border border-white/15 bg-[#111116] p-7">
            <div className="mb-6 flex items-start justify-between">
              <div>
                <p className="text-xs font-semibold uppercase text-purple-300">
                  New learning goal
                </p>
                <h2 className="mt-1 text-2xl font-bold text-white">
                  Define the outcome
                </h2>
              </div>
              <button
                type="button"
                onClick={() => setShowWizard(false)}
                className="rounded-lg p-2 text-gray-400 hover:bg-white/10"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <form onSubmit={submitGoal} className="space-y-4">
              <Field label="Goal title" name="title" required />
              <label className="block text-xs font-medium text-gray-300">
                What do you want to achieve?
                <textarea
                  name="raw_statement"
                  required
                  minLength={5}
                  rows={3}
                  className="mt-1.5 w-full rounded-lg border border-white/10 bg-black/40 p-3 text-sm text-white outline-none focus:border-purple-500"
                />
              </label>
              <Field label="Supporting context" name="description" />
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="Category" name="category" />
                <Field label="Target date" name="target_date" type="date" required />
                <label className="block text-xs font-medium text-gray-300">
                  Priority
                  <select
                    name="priority"
                    defaultValue="3"
                    className="mt-1.5 w-full rounded-lg border border-white/10 bg-black/40 p-3 text-sm text-white"
                  >
                    {[1, 2, 3, 4, 5].map((value) => (
                      <option key={value} value={value}>{value}</option>
                    ))}
                  </select>
                </label>
              </div>
              <label className="block text-xs font-medium text-gray-300">
                Success criteria, one per line
                <textarea
                  name="success_criteria"
                  rows={3}
                  className="mt-1.5 w-full rounded-lg border border-white/10 bg-black/40 p-3 text-sm text-white outline-none focus:border-purple-500"
                />
              </label>
              <button
                type="submit"
                disabled={busy}
                className="w-full rounded-lg bg-purple-600 py-3 text-sm font-bold text-white hover:bg-purple-500 disabled:opacity-60"
              >
                {busy ? 'Building goal and plan...' : 'Create and generate plan'}
              </button>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

const Tab = ({ active, children, ...props }) => (
  <button
    type="button"
    {...props}
    className={`rounded-lg px-4 py-2 text-xs font-bold ${
      active ? 'bg-purple-600 text-white' : 'bg-white/5 text-gray-400'
    }`}
  >
    {children}
  </button>
);

const Field = ({ label, ...props }) => (
  <label className="block text-xs font-medium text-gray-300">
    {label}
    <input
      {...props}
      className="mt-1.5 w-full rounded-lg border border-white/10 bg-black/40 p-3 text-sm text-white outline-none focus:border-purple-500"
    />
  </label>
);

const EmptyRow = ({ text }) => (
  <div className="border-y border-white/10 py-12 text-center text-sm text-gray-500">
    {text}
  </div>
);

const Metric = ({ label, value }) => (
  <div>
    <div className="text-xs text-gray-500">{label}</div>
    <div className="mt-1 text-sm font-bold capitalize text-white">{value}</div>
  </div>
);
