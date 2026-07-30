import React from 'react';
import { AppProvider, useApp } from './context/AppContext';
import { AppShell } from './components/layout/AppShell';
import LandingPage from './components/LandingPage';
import { AuthDialog } from './components/AuthDialog';

// Student Component Imports
import { StudentDashboard } from './components/student/StudentDashboard';
import { GoalsView } from './components/student/GoalsView';
import { TodayPlanner } from './components/student/TodayPlanner';
import { FocusTimerView } from './components/student/FocusTimerView';
import { TutorChatView } from './components/student/TutorChatView';
import { AssessmentsView } from './components/student/AssessmentsView';
import { EvidenceCenter } from './components/student/EvidenceCenter';
import { ProgressMasteryView } from './components/student/ProgressMasteryView';
import { OnboardingView } from './components/student/OnboardingView';

// Admin Component Imports
import { AdminDashboard } from './components/admin/AdminDashboard';
import { AgentsRegistryView } from './components/admin/AgentsRegistryView';
import { ReviewQueueView } from './components/admin/ReviewQueueView';

const MainContent = () => {
  const {
    appMode,
    studentTab,
    adminTab,
    user,
    studentProfile,
    booting,
  } = useApp();

  if (booting) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center text-sm text-gray-400">
        Loading your AstraPath workspace...
      </div>
    );
  }

  if (appMode === 'landing' || !user) {
    return <LandingPage />;
  }

  if (user.role === 'student') {
    if (!studentProfile) return <OnboardingView />;
    switch (studentTab) {
      case 'dashboard': return <StudentDashboard />;
      case 'goals': return <GoalsView />;
      case 'today': return <TodayPlanner />;
      case 'focus': return <FocusTimerView />;
      case 'tutor': return <TutorChatView />;
      case 'assessments': return <AssessmentsView />;
      case 'evidence': return <EvidenceCenter />;
      case 'progress': return <ProgressMasteryView />;
      default: return <StudentDashboard />;
    }
  }

  if (user.role === 'admin') {
    switch (adminTab) {
      case 'dashboard': return <AdminDashboard />;
      case 'agents': return <AgentsRegistryView />;
      case 'reviews': return <ReviewQueueView />;
      default: return <AdminDashboard />;
    }
  }

  return <LandingPage />;
};

function App() {
  return (
    <AppProvider>
      <AppShell>
        <MainContent />
      </AppShell>
      <AuthDialog />
    </AppProvider>
  );
}

export default App;
