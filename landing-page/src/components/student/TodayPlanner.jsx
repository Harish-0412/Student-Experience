import React from 'react';
import { useApp } from '../../context/AppContext';
import { Calendar, Check, Play } from 'lucide-react';

const categories = ['Essential', 'Recommended', 'Stretch'];

const formatSchedule = (value) =>
  value
    ? new Date(value).toLocaleTimeString([], {
        hour: '2-digit',
        minute: '2-digit',
      })
    : 'Not scheduled today';

export const TodayPlanner = () => {
  const {
    tasks,
    dailyPlan,
    plan,
    toggleTaskCompletion,
    selectFocusTask,
    setStudentTab,
  } = useApp();

  return (
    <div className="mx-auto max-w-7xl space-y-8 pb-12">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <h1 className="flex items-center gap-3 text-3xl font-extrabold text-white">
            <Calendar className="h-8 w-8 text-purple-400" />
            Today&apos;s Action Plan
          </h1>
          <p className="mt-2 text-sm text-gray-400">
            {dailyPlan
              ? `${dailyPlan.date} · ${dailyPlan.timezone}`
              : 'No daily plan is available for today.'}
          </p>
        </div>
        {dailyPlan && (
          <div className="text-right">
            <div className="text-xs text-gray-500">Planned load</div>
            <div className="text-xl font-bold text-white">
              {dailyPlan.total_minutes} minutes
            </div>
          </div>
        )}
      </div>

      {dailyPlan?.capacity_warning && (
        <div className="rounded-lg border border-amber-500/25 bg-amber-500/10 p-4 text-xs text-amber-200">
          {dailyPlan.capacity_warning}
        </div>
      )}

      {tasks.length ? (
        <div className="space-y-7">
          {categories.map((category) => {
            const categoryTasks = tasks.filter(
              (task) => task.category === category,
            );
            if (!categoryTasks.length) return null;
            return (
              <section key={category}>
                <h2 className="mb-2 text-xs font-bold uppercase text-purple-300">
                  {category} · {categoryTasks.length}
                </h2>
                <div className="divide-y divide-white/10 border-y border-white/10">
                  {categoryTasks.map((task) => (
                    <div
                      key={task.id}
                      className="flex flex-col justify-between gap-4 py-5 sm:flex-row sm:items-center"
                    >
                      <div className="flex items-start gap-3">
                        <button
                          type="button"
                          disabled={task.status === 'completed'}
                          onClick={() => toggleTaskCompletion(task.id)}
                          className={`mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-md border ${
                            task.status === 'completed'
                              ? 'border-emerald-500 bg-emerald-500 text-black'
                              : 'border-white/20 hover:border-purple-400'
                          }`}
                          title={
                            task.status === 'completed'
                              ? 'Task completed'
                              : 'Mark task complete'
                          }
                        >
                          {task.status === 'completed' && (
                            <Check className="h-4 w-4" />
                          )}
                        </button>
                        <div>
                          <h3
                            className={`text-sm font-bold ${
                              task.status === 'completed'
                                ? 'text-gray-500 line-through'
                                : 'text-white'
                            }`}
                          >
                            {task.title}
                          </h3>
                          <p className="mt-1 text-xs text-gray-500">
                            {formatSchedule(task.scheduledTime)} ·{' '}
                            {task.estimatedMinutes} min · {task.competency}
                          </p>
                          <p className="mt-2 max-w-3xl text-xs text-gray-400">
                            {task.explanation}
                          </p>
                        </div>
                      </div>
                      {task.status !== 'completed' && (
                        <button
                          type="button"
                          onClick={() => selectFocusTask(task)}
                          className="flex shrink-0 items-center justify-center gap-2 rounded-lg bg-purple-600 px-4 py-2 text-xs font-bold text-white hover:bg-purple-500"
                        >
                          <Play className="h-3.5 w-3.5 fill-current" />
                          Start focus
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              </section>
            );
          })}
        </div>
      ) : (
        <div className="border-y border-white/10 py-14 text-center">
          <p className="text-sm text-gray-500">
            {plan?.status === 'proposed'
              ? 'Approve the proposed plan before starting execution.'
              : 'There are no tasks scheduled for this view.'}
          </p>
          <button
            type="button"
            onClick={() => setStudentTab('goals')}
            className="mt-4 text-xs font-bold text-purple-300"
          >
            Open goals and roadmap
          </button>
        </div>
      )}
    </div>
  );
};
