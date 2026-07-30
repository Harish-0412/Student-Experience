import React, { useEffect, useMemo, useState } from 'react';
import { useApp } from '../../context/AppContext';
import {
  ArrowLeft,
  Brain,
  CheckCircle,
  Pause,
  Play,
  RotateCcw,
} from 'lucide-react';

export const FocusTimerView = () => {
  const {
    selectedGoal,
    focusState,
    setFocusState,
    beginFocusSession,
    completeFocusSession,
    setStudentTab,
  } = useApp();
  const [seconds, setSeconds] = useState(focusState.secondsRemaining);
  const [isActive, setIsActive] = useState(false);
  const [starting, setStarting] = useState(false);
  const [reflectionOpen, setReflectionOpen] = useState(false);
  const [sessionError, setSessionError] = useState('');

  useEffect(() => {
    setSeconds(focusState.secondsRemaining);
    setIsActive(false);
    setReflectionOpen(false);
  }, [
    focusState.task?.id,
    focusState.durationMinutes,
    focusState.secondsRemaining,
  ]);

  useEffect(() => {
    if (!isActive || seconds <= 0) return undefined;
    const interval = window.setInterval(
      () => setSeconds((value) => value - 1),
      1000,
    );
    return () => window.clearInterval(interval);
  }, [isActive, seconds]);

  useEffect(() => {
    if (seconds === 0 && isActive) {
      setIsActive(false);
      setReflectionOpen(true);
    }
  }, [isActive, seconds]);

  const detailItems = useMemo(
    () =>
      [
        focusState.task?.description,
        focusState.task?.evidenceDescription,
      ].filter(Boolean),
    [focusState.task],
  );

  const toggleTimer = async () => {
    setSessionError('');
    if (isActive) {
      setIsActive(false);
      return;
    }
    setStarting(true);
    try {
      await beginFocusSession();
      setIsActive(true);
    } catch (requestError) {
      setSessionError(requestError.message);
    } finally {
      setStarting(false);
    }
  };

  const resetTimer = () => {
    setIsActive(false);
    setSeconds(focusState.durationMinutes * 60);
  };

  const setDuration = (minutes) => {
    if (focusState.session) return;
    setFocusState((current) => ({
      ...current,
      durationMinutes: minutes,
      secondsRemaining: minutes * 60,
    }));
  };

  const submitReflection = async (event) => {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const elapsed = Math.max(
      1,
      Math.ceil((focusState.durationMinutes * 60 - seconds) / 60),
    );
    await completeFocusSession(
      data.get('reflection'),
      data.get('accomplished') === 'yes',
      elapsed,
    );
    setReflectionOpen(false);
    setStudentTab('dashboard');
  };

  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  const time = `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;

  if (!selectedGoal) {
    return (
      <div className="mx-auto max-w-3xl py-20 text-center text-sm text-gray-500">
        Create and select a goal before starting a focus session.
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl space-y-8 pb-12">
      <div className="flex items-center justify-between">
        <button
          type="button"
          onClick={() => setStudentTab('dashboard')}
          className="flex items-center gap-1 text-xs font-semibold text-gray-400 hover:text-white"
        >
          <ArrowLeft className="h-4 w-4" /> Dashboard
        </button>
        <span className="text-xs text-purple-300">
          {focusState.session ? 'Session recording' : 'Ready to start'}
        </span>
      </div>

      <section className="space-y-7 border-y border-white/10 py-10 text-center">
        <div>
          <div className="text-xs uppercase text-gray-500">Objective</div>
          <h1 className="mt-2 text-xl font-bold text-white">
            {focusState.task?.title || selectedGoal.title}
          </h1>
        </div>

        <div className="font-mono text-7xl font-extrabold text-white md:text-8xl">
          {time}
        </div>

        <div className="flex items-center justify-center gap-2">
          {[25, 50].map((minutes) => (
            <button
              key={minutes}
              type="button"
              disabled={Boolean(focusState.session)}
              onClick={() => setDuration(minutes)}
              className={`rounded-lg px-3 py-2 text-xs font-bold ${
                focusState.durationMinutes === minutes
                  ? 'bg-purple-600 text-white'
                  : 'bg-white/5 text-gray-400'
              } disabled:opacity-50`}
            >
              {minutes} min
            </button>
          ))}
        </div>

        <div className="flex items-center justify-center gap-3">
          <button
            type="button"
            onClick={toggleTimer}
            disabled={starting}
            className={`flex items-center gap-2 rounded-lg px-7 py-3 text-sm font-bold ${
              isActive
                ? 'bg-amber-500 text-black'
                : 'bg-purple-600 text-white'
            } disabled:opacity-60`}
          >
            {isActive ? (
              <Pause className="h-5 w-5 fill-current" />
            ) : (
              <Play className="h-5 w-5 fill-current" />
            )}
            {starting ? 'Starting...' : isActive ? 'Pause' : 'Start focus'}
          </button>
          <button
            type="button"
            onClick={resetTimer}
            className="rounded-lg border border-white/10 p-3 text-gray-300 hover:bg-white/5"
            title="Reset timer"
          >
            <RotateCcw className="h-5 w-5" />
          </button>
          {focusState.session && (
            <button
              type="button"
              onClick={() => {
                setIsActive(false);
                setReflectionOpen(true);
              }}
              className="rounded-lg border border-emerald-500/30 px-4 py-3 text-xs font-bold text-emerald-300"
            >
              Finish now
            </button>
          )}
        </div>
        {sessionError && <p className="text-xs text-rose-300">{sessionError}</p>}
      </section>

      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-bold text-white">Task context</h2>
          <button
            type="button"
            onClick={() => setStudentTab('tutor')}
            className="flex items-center gap-1 text-xs font-semibold text-purple-300"
          >
            <Brain className="h-4 w-4" /> Ask tutor
          </button>
        </div>
        {detailItems.length ? (
          <ul className="divide-y divide-white/10 border-y border-white/10">
            {detailItems.map((item) => (
              <li key={item} className="py-4 text-sm text-gray-300">
                {item}
              </li>
            ))}
          </ul>
        ) : (
          <p className="border-y border-white/10 py-6 text-sm text-gray-500">
            No additional task context was supplied.
          </p>
        )}
      </section>

      {reflectionOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/85 p-4 backdrop-blur-md">
          <form
            onSubmit={submitReflection}
            className="w-full max-w-lg space-y-5 rounded-2xl border border-white/15 bg-[#111116] p-7"
          >
            <CheckCircle className="h-8 w-8 text-emerald-400" />
            <div>
              <h2 className="text-2xl font-bold text-white">Session reflection</h2>
              <p className="mt-1 text-xs text-gray-400">
                This reflection is stored with the completed focus record.
              </p>
            </div>
            <label className="block text-xs font-medium text-gray-300">
              What changed during this session?
              <textarea
                name="reflection"
                rows={4}
                maxLength={2000}
                className="mt-1.5 w-full rounded-lg border border-white/10 bg-black/40 p-3 text-sm text-white outline-none focus:border-purple-500"
              />
            </label>
            <label className="block text-xs font-medium text-gray-300">
              Outcome
              <select
                name="accomplished"
                defaultValue="yes"
                className="mt-1.5 w-full rounded-lg border border-white/10 bg-black/40 p-3 text-sm text-white"
              >
                <option value="yes">Objective accomplished</option>
                <option value="no">Objective needs more work</option>
              </select>
            </label>
            <button
              type="submit"
              className="w-full rounded-lg bg-purple-600 py-3 text-sm font-bold text-white"
            >
              Save completed session
            </button>
          </form>
        </div>
      )}
    </div>
  );
};
