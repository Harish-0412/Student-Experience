import React, { useState } from 'react';
import { LogIn, UserPlus, X } from 'lucide-react';
import { useApp } from '../context/AppContext';

export const AuthDialog = () => {
  const {
    authDialog,
    setAuthDialog,
    authenticate,
    busy,
    error,
    clearError,
  } = useApp();
  const [formError, setFormError] = useState('');

  if (!authDialog) return null;
  const registering = authDialog === 'register';

  const submit = async (event) => {
    event.preventDefault();
    setFormError('');
    const data = new FormData(event.currentTarget);
    try {
      await authenticate(
        authDialog,
        registering
          ? {
              full_name: data.get('full_name'),
              email: data.get('email'),
              password: data.get('password'),
            }
          : {
              email: data.get('email'),
              password: data.get('password'),
            },
      );
    } catch (requestError) {
      setFormError(requestError.message);
    }
  };

  const close = () => {
    clearError();
    setFormError('');
    setAuthDialog(null);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4 backdrop-blur-md">
      <div className="w-full max-w-md rounded-2xl border border-white/15 bg-[#111116] p-7 shadow-2xl">
        <div className="mb-6 flex items-start justify-between">
          <div>
            <p className="text-xs font-semibold uppercase text-purple-300">
              {registering ? 'Student registration' : 'Secure access'}
            </p>
            <h2 className="mt-1 text-2xl font-bold text-white">
              {registering ? 'Create your AstraPath account' : 'Sign in'}
            </h2>
          </div>
          <button
            type="button"
            onClick={close}
            className="rounded-lg p-2 text-gray-400 hover:bg-white/10 hover:text-white"
            aria-label="Close"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <form onSubmit={submit} className="space-y-4">
          {registering && (
            <label className="block text-xs font-medium text-gray-300">
              Full name
              <input
                name="full_name"
                required
                minLength={2}
                className="mt-1.5 w-full rounded-lg border border-white/10 bg-black/40 p-3 text-sm text-white outline-none focus:border-purple-500"
              />
            </label>
          )}
          <label className="block text-xs font-medium text-gray-300">
            Email
            <input
              name="email"
              type="email"
              autoComplete="email"
              required
              className="mt-1.5 w-full rounded-lg border border-white/10 bg-black/40 p-3 text-sm text-white outline-none focus:border-purple-500"
            />
          </label>
          <label className="block text-xs font-medium text-gray-300">
            Password
            <input
              name="password"
              type="password"
              autoComplete={registering ? 'new-password' : 'current-password'}
              minLength={12}
              required
              className="mt-1.5 w-full rounded-lg border border-white/10 bg-black/40 p-3 text-sm text-white outline-none focus:border-purple-500"
            />
          </label>

          {(formError || error) && (
            <p className="rounded-lg border border-rose-500/30 bg-rose-500/10 p-3 text-xs text-rose-200">
              {formError || error}
            </p>
          )}

          <button
            type="submit"
            disabled={busy}
            className="flex w-full items-center justify-center gap-2 rounded-lg bg-purple-600 py-3 text-sm font-bold text-white hover:bg-purple-500 disabled:cursor-wait disabled:opacity-60"
          >
            {registering ? (
              <UserPlus className="h-4 w-4" />
            ) : (
              <LogIn className="h-4 w-4" />
            )}
            {busy
              ? 'Connecting...'
              : registering
                ? 'Create student account'
                : 'Sign in'}
          </button>
        </form>

        <button
          type="button"
          onClick={() => {
            clearError();
            setFormError('');
            setAuthDialog(registering ? 'login' : 'register');
          }}
          className="mt-5 w-full text-center text-xs text-purple-300 hover:text-purple-200"
        >
          {registering
            ? 'Already have an account? Sign in'
            : 'New student? Create an account'}
        </button>
      </div>
    </div>
  );
};
