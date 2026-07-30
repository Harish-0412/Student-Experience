import React, { useState } from 'react';
import { CalendarClock, GraduationCap } from 'lucide-react';
import { useApp } from '../../context/AppContext';

const weekdays = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday'];

export const OnboardingView = () => {
  const { user, completeOnboarding, busy, error } = useApp();
  const [selectedDays, setSelectedDays] = useState(weekdays);

  const submit = async (event) => {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const start = data.get('start');
    const end = data.get('end');
    const availability = Object.fromEntries(
      selectedDays.map((day) => [day, [{ start, end, energy: 'medium' }]]),
    );
    await completeOnboarding({
      display_name: data.get('display_name'),
      timezone: data.get('timezone'),
      locale: 'en-IN',
      education_level: data.get('education_level') || null,
      institution: data.get('institution') || null,
      weekly_learning_minutes: Number(data.get('weekly_learning_minutes')),
      learning_preferences: [],
      availability,
      device_access: [],
      accessibility_needs: [],
      consent_scopes: [],
      onboarding_completed: true,
    });
  };

  return (
    <div className="mx-auto max-w-3xl space-y-7 pb-12">
      <div>
        <div className="mb-3 flex h-11 w-11 items-center justify-center rounded-lg border border-purple-500/30 bg-purple-500/15 text-purple-300">
          <GraduationCap className="h-5 w-5" />
        </div>
        <h1 className="text-3xl font-extrabold text-white">
          Set up your learning profile
        </h1>
        <p className="mt-2 text-sm text-gray-400">
          Planning capacity and availability are used by the feasibility and
          scheduling services.
        </p>
      </div>

      <form
        onSubmit={submit}
        className="space-y-6 border-t border-white/10 pt-6"
      >
        <div className="grid gap-4 md:grid-cols-2">
          <Field
            label="Display name"
            name="display_name"
            defaultValue={user?.full_name || ''}
            required
          />
          <Field
            label="Timezone"
            name="timezone"
            defaultValue="Asia/Kolkata"
            required
          />
          <Field
            label="Education level"
            name="education_level"
            placeholder="Undergraduate"
          />
          <Field label="Institution" name="institution" />
          <Field
            label="Weekly learning minutes"
            name="weekly_learning_minutes"
            type="number"
            min="30"
            max="10080"
            defaultValue="300"
            required
          />
        </div>

        <div className="space-y-3">
          <div className="flex items-center gap-2 text-sm font-bold text-white">
            <CalendarClock className="h-4 w-4 text-purple-300" />
            Recurring availability
          </div>
          <div className="flex flex-wrap gap-2">
            {weekdays.map((day) => {
              const selected = selectedDays.includes(day);
              return (
                <label
                  key={day}
                  className={`cursor-pointer rounded-lg border px-3 py-2 text-xs capitalize ${
                    selected
                      ? 'border-purple-500/50 bg-purple-500/15 text-purple-200'
                      : 'border-white/10 bg-white/5 text-gray-400'
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={selected}
                    onChange={() =>
                      setSelectedDays((days) =>
                        selected
                          ? days.filter((item) => item !== day)
                          : [...days, day],
                      )
                    }
                    className="sr-only"
                  />
                  {day}
                </label>
              );
            })}
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Start time" name="start" type="time" defaultValue="18:00" required />
            <Field label="End time" name="end" type="time" defaultValue="19:00" required />
          </div>
        </div>

        {error && (
          <p className="rounded-lg border border-rose-500/30 bg-rose-500/10 p-3 text-xs text-rose-200">
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={busy || selectedDays.length === 0}
          className="rounded-lg bg-purple-600 px-6 py-3 text-sm font-bold text-white hover:bg-purple-500 disabled:opacity-50"
        >
          {busy ? 'Saving profile...' : 'Complete onboarding'}
        </button>
      </form>
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
