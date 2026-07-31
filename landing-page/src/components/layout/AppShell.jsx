import React from 'react';
import { useApp } from '../../context/AppContext';
import {
  Activity,
  Award,
  Calendar,
  Cpu,
  LayoutDashboard,
  LogIn,
  LogOut,
  MessageSquare,
  RefreshCw,
  ShieldAlert,
  ShieldCheck,
  Target,
  TrendingUp,
  UserPlus,
  Zap,
} from 'lucide-react';

export const AppShell = ({ children }) => {
  const {
    appMode,
    setAppMode,
    user,
    logout,
    setAuthDialog,
    studentTab,
    setStudentTab,
    adminTab,
    setAdminTab,
    studentProfile,
    selectedGoal,
    progress,
    agents,
    busy,
    error,
    clearError,
    refreshPortal,
  } = useApp();

  const studentNavItems = [
    { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { id: 'goals', label: 'Goals & Roadmap', icon: Target },
    { id: 'today', label: 'Today Planner', icon: Calendar },
    { id: 'focus', label: 'Focus Mode', icon: Zap },
    { id: 'tutor', label: 'AI Tutor', icon: MessageSquare },
    { id: 'assessments', label: 'Assessments', icon: Award },
    { id: 'evidence', label: 'Evidence Center', icon: ShieldCheck },
    { id: 'progress', label: 'Progress & Mastery', icon: TrendingUp },
  ];
  const adminNavItems = [
    { id: 'dashboard', label: 'Admin Dashboard', icon: LayoutDashboard },
    { id: 'agents', label: 'Agent Registry', icon: Cpu },
    { id: 'reviews', label: 'Review Queue', icon: ShieldAlert },
  ];
  const portalMode = user?.role;
  const inPortal = portalMode && appMode === portalMode;
  const navItems = portalMode === 'student' ? studentNavItems : adminNavItems;

  const navigate = (item) => {
    if (portalMode === 'student') setStudentTab(item.id);
    if (portalMode === 'admin') setAdminTab(item.id);
  };

  return (
    <div className="flex min-h-screen flex-col bg-[#0a0a0c] font-sans text-white selection:bg-purple-500 selection:text-white">
      <header className="sticky top-0 z-40 flex min-h-16 items-center justify-between border-b border-white/10 bg-black/70 px-4 py-3 backdrop-blur-xl md:px-6">
        <button
          type="button"
          onClick={() => setAppMode('landing')}
          className="flex items-center gap-2"
        >
          <span className="h-4 w-4 rotate-45 rounded-sm bg-purple-500" />
          <span className="text-xl font-extrabold text-white">AstraPath</span>
        </button>

        <div className="flex items-center gap-2">
          {user ? (
            <>
              {inPortal && (
                <button
                  type="button"
                  onClick={refreshPortal}
                  disabled={busy}
                  className="rounded-lg p-2 text-gray-400 hover:bg-white/10 hover:text-white disabled:opacity-50"
                  title="Refresh portal data"
                >
                  <RefreshCw className={`h-4 w-4 ${busy ? 'animate-spin' : ''}`} />
                </button>
              )}
              <button
                type="button"
                onClick={() => setAppMode(portalMode)}
                className="rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-xs font-semibold text-gray-200 hover:bg-white/10"
              >
                {portalMode === 'student' ? 'Student portal' : 'Admin operations'}
              </button>
              <div className="hidden text-right sm:block">
                <div className="text-xs font-bold text-white">
                  {studentProfile?.display_name || user.full_name}
                </div>
                <div className="text-[10px] uppercase text-purple-300">
                  {user.role}
                </div>
              </div>
              <button
                type="button"
                onClick={logout}
                className="rounded-lg p-2 text-gray-400 hover:bg-white/10 hover:text-white"
                title="Sign out"
              >
                <LogOut className="h-4 w-4" />
              </button>
            </>
          ) : (
            <>
              <button
                type="button"
                onClick={() => setAuthDialog('login')}
                className="flex items-center gap-2 rounded-lg border border-white/15 bg-white/5 px-3 py-2 text-xs font-semibold text-white hover:bg-white/10"
              >
                <LogIn className="h-4 w-4" /> Sign in
              </button>
              <button
                type="button"
                onClick={() => setAuthDialog('register')}
                className="hidden items-center gap-2 rounded-lg bg-purple-600 px-3 py-2 text-xs font-semibold text-white hover:bg-purple-500 sm:flex"
              >
                <UserPlus className="h-4 w-4" /> Register
              </button>
            </>
          )}
        </div>
      </header>

      {error && (
        <div className="flex items-center justify-between border-b border-rose-500/20 bg-rose-500/10 px-6 py-2 text-xs text-rose-200">
          <span>{error}</span>
          <button type="button" onClick={clearError} className="font-bold">
            Dismiss
          </button>
        </div>
      )}

      {!inPortal ? (
        <div className="flex-1">{children}</div>
      ) : (
        <div className="flex flex-1">
          <aside className="hidden w-64 shrink-0 flex-col justify-between border-r border-white/10 bg-black/40 p-4 md:flex">
            <div className="space-y-6">
              {portalMode === 'student' && selectedGoal && (
                <div className="space-y-1 border-l-2 border-purple-500 px-3 py-1">
                  <div className="text-[10px] font-bold uppercase text-purple-300">
                    Active goal
                  </div>
                  <div className="truncate text-xs font-bold text-white">
                    {selectedGoal.title}
                  </div>
                  {progress && (
                    <div className="text-[10px] text-emerald-400">
                      {Math.round(progress.goal_confidence)}% confidence
                    </div>
                  )}
                </div>
              )}

              <nav className="space-y-1">
                {navItems.map((item) => {
                  const Icon = item.icon;
                  const active =
                    portalMode === 'student'
                      ? studentTab === item.id
                      : adminTab === item.id;
                  return (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() => navigate(item)}
                      className={`flex w-full items-center gap-3 rounded-lg px-4 py-3 text-xs font-semibold transition-colors ${
                        active
                          ? 'bg-purple-600 text-white'
                          : 'text-gray-400 hover:bg-white/5 hover:text-white'
                      }`}
                    >
                      <Icon className="h-4 w-4" />
                      {item.label}
                    </button>
                  );
                })}
              </nav>
            </div>

            <div className="flex items-center gap-2 border-t border-white/10 pt-4 text-[10px] text-gray-500">
              <Activity className="h-3.5 w-3.5" />
              {agents.length
                ? `${agents.length} implemented agents registered`
                : 'Phase 1-4 services connected'}
            </div>
          </aside>

          <div className="min-w-0 flex-1">
            <nav className="flex gap-1 overflow-x-auto border-b border-white/10 bg-black/30 p-2 md:hidden">
              {navItems.map((item) => {
                const Icon = item.icon;
                return (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => navigate(item)}
                    className="flex shrink-0 items-center gap-2 rounded-lg px-3 py-2 text-xs text-gray-300 hover:bg-white/10"
                  >
                    <Icon className="h-4 w-4" />
                    {item.label}
                  </button>
                );
              })}
            </nav>
            <main className="p-4 md:p-8">{children}</main>
          </div>
        </div>
      )}
    </div>
  );
};
