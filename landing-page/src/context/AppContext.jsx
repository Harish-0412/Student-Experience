/* oxlint-disable react/only-export-components */
import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';
import { api, ApiError, readSession, writeSession } from '../lib/api';

export const AppContext = createContext(null);

const today = () => new Date().toISOString().slice(0, 10);

const optional = async (operation, fallback = null) => {
  try {
    return await operation();
  } catch (error) {
    if (
      error instanceof ApiError &&
      (error.status === 404 || error.status === 409)
    ) {
      return fallback;
    }
    throw error;
  }
};

const messageFor = (error) =>
  error instanceof Error ? error.message : 'An unexpected request error occurred.';

const emptyFocusState = {
  task: null,
  session: null,
  durationMinutes: 25,
  secondsRemaining: 25 * 60,
};

export const AppProvider = ({ children }) => {
  const initialSession = readSession();
  const [session, setSession] = useState(initialSession);
  const [user, setUser] = useState(initialSession?.user || null);
  const [appMode, setAppMode] = useState(
    initialSession?.user?.role || 'landing',
  );
  const [studentTab, setStudentTab] = useState('dashboard');
  const [adminTab, setAdminTab] = useState('dashboard');
  const [authDialog, setAuthDialog] = useState(null);
  const [booting, setBooting] = useState(Boolean(initialSession));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const [studentProfile, setStudentProfile] = useState(null);
  const [goalTemplates, setGoalTemplates] = useState([]);
  const [goals, setGoals] = useState([]);
  const [selectedGoalId, setSelectedGoalId] = useState(null);
  const [goalGraph, setGoalGraph] = useState(null);
  const [competencies, setCompetencies] = useState([]);
  const [plan, setPlan] = useState(null);
  const [dailyPlan, setDailyPlan] = useState(null);
  const [progress, setProgress] = useState(null);
  const [masteryData, setMasteryData] = useState([]);
  const [risks, setRisks] = useState([]);
  const [assessments, setAssessments] = useState([]);
  const [evidence, setEvidence] = useState([]);
  const [notifications, setNotifications] = useState([]);
  const [focusState, setFocusState] = useState(emptyFocusState);
  const [conversations, setConversations] = useState([]);
  const [activeConvId, setActiveConvId] = useState(null);
  const [tutorBusy, setTutorBusy] = useState(false);

  const [students, setStudents] = useState([]);
  const [agents, setAgents] = useState([]);
  const [agentRuns, setAgentRuns] = useState([]);
  const [reviewItems, setReviewItems] = useState([]);
  const [systemHealth, setSystemHealth] = useState(null);
  const [operationsStatus, setOperationsStatus] = useState(null);
  const [securityPolicy, setSecurityPolicy] = useState(null);

  const resetGoalData = useCallback(() => {
    setGoalGraph(null);
    setCompetencies([]);
    setPlan(null);
    setDailyPlan(null);
    setProgress(null);
    setMasteryData([]);
    setRisks([]);
    setAssessments([]);
    setEvidence([]);
    setNotifications([]);
  }, []);

  const loadStudentBase = useCallback(async () => {
    const [profile, templates] = await Promise.all([
      optional(api.profile, null),
      api.goalTemplates(),
    ]);
    setStudentProfile(profile);
    setGoalTemplates(templates);
    if (!profile) {
      setGoals([]);
      setSelectedGoalId(null);
      resetGoalData();
      return;
    }
    const goalList = await api.goals();
    setGoals(goalList);
    setSelectedGoalId((current) => {
      if (goalList.some((goal) => goal.id === current)) return current;
      return goalList[0]?.id || null;
    });
  }, [resetGoalData]);

  const loadGoalData = useCallback(async (goalId) => {
    if (!goalId) {
      resetGoalData();
      return;
    }
    const progressRequest = async () => {
      const existing = await optional(() => api.progress(goalId), null);
      return existing || optional(() => api.rebuildProgress(goalId), null);
    };
    const [
      graph,
      goalCompetencies,
      currentPlan,
      currentDailyPlan,
      currentProgress,
      currentMastery,
      currentRisks,
      currentAssessments,
      currentEvidence,
      currentNotifications,
    ] = await Promise.all([
      optional(() => api.graph(goalId), null),
      optional(() => api.competencies(goalId), []),
      optional(() => api.plan(goalId), null),
      optional(() => api.dailyPlan(today()), null),
      progressRequest(),
      api.mastery(goalId),
      api.risks(goalId),
      api.assessments(goalId),
      api.evidence(goalId),
      api.notifications(),
    ]);
    setGoalGraph(graph);
    setCompetencies(goalCompetencies);
    setPlan(currentPlan);
    setDailyPlan(currentDailyPlan);
    setProgress(currentProgress);
    setMasteryData(currentMastery);
    setRisks(currentRisks);
    setAssessments(currentAssessments);
    setEvidence(currentEvidence);
    setNotifications(currentNotifications);
  }, [resetGoalData]);

  const loadAdmin = useCallback(async () => {
    const [
      userList,
      phase123Agents,
      phase4Agents,
      runs,
      queue,
      health,
      operations,
      policy,
    ] = await Promise.all([
      api.users(),
      api.phase123Agents(),
      api.phase4Agents(),
      api.agentRuns(),
      api.reviewQueue(),
      api.health(),
      api.operationsStatus(),
      api.securityPolicy(),
    ]);
    const runSummary = new Map();
    runs.forEach((run) => {
      const current = runSummary.get(run.agent_name) || {
        count: 0,
        latest: null,
      };
      current.count += 1;
      if (!current.latest || run.started_at > current.latest.started_at) {
        current.latest = run;
      }
      runSummary.set(run.agent_name, current);
    });
    const normalizeAgent = (agent, phase) => {
      const run = runSummary.get(agent.name);
      return {
        ...agent,
        phase,
        runCount: run?.count || 0,
        lastStatus: run?.latest?.status || 'not_run',
        lastRunAt: run?.latest?.started_at || null,
      };
    };
    setStudents(userList.items.filter((item) => item.role === 'student'));
    setAgentRuns(runs);
    setAgents([
      ...phase123Agents.map((agent) => normalizeAgent(agent, 'Phases 1-3')),
      ...phase4Agents.map((agent) => normalizeAgent(agent, 'Phase 4')),
    ]);
    setReviewItems(queue);
    setSystemHealth(health);
    setOperationsStatus(operations);
    setSecurityPolicy(policy);
  }, []);

  const hydrate = useCallback(async (identity) => {
    if (identity.role === 'student') {
      await loadStudentBase();
    } else if (identity.role === 'admin') {
      await loadAdmin();
    }
  }, [loadAdmin, loadStudentBase]);

  useEffect(() => {
    if (!session?.access_token) {
      setBooting(false);
      return undefined;
    }
    let cancelled = false;
    setBooting(true);
    api.me()
      .then(async (identity) => {
        if (cancelled) return;
        setUser(identity);
        setAppMode(identity.role);
        await hydrate(identity);
      })
      .catch((requestError) => {
        if (cancelled) return;
        writeSession(null);
        setSession(null);
        setUser(null);
        setAppMode('landing');
        setError(messageFor(requestError));
      })
      .finally(() => {
        if (!cancelled) setBooting(false);
      });
    return () => {
      cancelled = true;
    };
  }, [hydrate, session?.access_token]);

  useEffect(() => {
    if (
      user?.role !== 'student' ||
      !studentProfile ||
      !selectedGoalId
    ) {
      if (!selectedGoalId) resetGoalData();
      return;
    }
    let cancelled = false;
    setBusy(true);
    loadGoalData(selectedGoalId)
      .catch((requestError) => {
        if (!cancelled) setError(messageFor(requestError));
      })
      .finally(() => {
        if (!cancelled) setBusy(false);
      });
    return () => {
      cancelled = true;
    };
  }, [
    loadGoalData,
    resetGoalData,
    selectedGoalId,
    studentProfile,
    user?.role,
  ]);

  const authenticate = async (mode, credentials) => {
    setBusy(true);
    setError('');
    try {
      const nextSession =
        mode === 'register'
          ? await api.register(credentials)
          : await api.login(credentials);
      writeSession(nextSession);
      setSession(nextSession);
      setUser(nextSession.user);
      setAppMode(nextSession.user.role);
      setAuthDialog(null);
    } catch (requestError) {
      setError(messageFor(requestError));
      throw requestError;
    } finally {
      setBusy(false);
    }
  };

  const logout = async () => {
    setBusy(true);
    try {
      if (session?.refresh_token) await api.logout(session.refresh_token);
    } catch {
      // Local session removal remains authoritative when the API is unavailable.
    } finally {
      writeSession(null);
      setSession(null);
      setUser(null);
      setAppMode('landing');
      setStudentProfile(null);
      setGoalTemplates([]);
      setGoals([]);
      setSelectedGoalId(null);
      resetGoalData();
      setStudents([]);
      setAgents([]);
      setReviewItems([]);
      setOperationsStatus(null);
      setSecurityPolicy(null);
      setBusy(false);
    }
  };

  const completeOnboarding = async (values) => {
    setBusy(true);
    setError('');
    try {
      const profile = await api.onboard(values);
      setStudentProfile(profile);
      await loadStudentBase();
      return profile;
    } catch (requestError) {
      setError(messageFor(requestError));
      throw requestError;
    } finally {
      setBusy(false);
    }
  };

  const addGoal = async (values) => {
    setBusy(true);
    setError('');
    try {
      const created = await api.createGoal({
        title: values.title,
        raw_statement: values.raw_statement || values.title,
        description: values.description || null,
        category: values.category || null,
        target_date: values.target_date,
        priority: Number(values.priority || 3),
        success_criteria: values.success_criteria || [],
        assumptions: values.assumptions || [],
      });
      const weeklyHours = Math.max(
        (studentProfile?.weekly_learning_minutes || 300) / 60,
        0.5,
      );
      await api.clarifyGoal(created.id, {
        raw_goal: `${created.title}. ${created.raw_statement}`,
        template_slug: values.template_slug,
        target_date: created.target_date,
        weekly_hours: weeklyHours,
      });
      await api.assessFeasibility(created.id, {
        target_date: created.target_date,
        weekly_hours: weeklyHours,
      });
      await api.analyzeSkillGap(created.id, {});
      const generatedPlan = await api.generatePlan(created.id, {});
      const goalList = await api.goals();
      setGoals(goalList);
      setSelectedGoalId(created.id);
      setPlan(generatedPlan);
      setStudentTab('goals');
      return generatedPlan;
    } catch (requestError) {
      setError(messageFor(requestError));
      const goalList = await optional(api.goals, []);
      setGoals(goalList);
      throw requestError;
    } finally {
      setBusy(false);
    }
  };

  const decidePlan = async (decision) => {
    if (!selectedGoalId || !plan) return;
    setBusy(true);
    setError('');
    try {
      const updated = await api.decidePlan(selectedGoalId, {
        decision,
        reason:
          decision === 'approve'
            ? 'Student approved the generated plan in the portal'
            : 'Student rejected the generated plan in the portal',
      });
      setPlan(updated);
      const currentGoal = goals.find((goal) => goal.id === selectedGoalId);
      if (decision === 'approve' && currentGoal?.status === 'draft') {
        const activatedGoal = await api.activateGoal(selectedGoalId, {
          expected_version: currentGoal.version,
          reason: 'Student approved the first executable learning plan',
        });
        setGoals((current) =>
          current.map((goal) =>
            goal.id === activatedGoal.id ? activatedGoal : goal,
          ),
        );
      }
    } catch (requestError) {
      setError(messageFor(requestError));
      throw requestError;
    } finally {
      setBusy(false);
    }
  };

  const regeneratePlan = async () => {
    if (!selectedGoalId) return null;
    setBusy(true);
    setError('');
    try {
      const generatedPlan = await api.generatePlan(selectedGoalId, {});
      setPlan(generatedPlan);
      return generatedPlan;
    } catch (requestError) {
      setError(messageFor(requestError));
      throw requestError;
    } finally {
      setBusy(false);
    }
  };

  const toggleTaskCompletion = async (taskId) => {
    const task = plan?.tasks.find((item) => item.id === taskId);
    if (!task || task.status === 'completed' || !selectedGoalId) return;
    setError('');
    try {
      const updated = await api.updateTaskStatus(selectedGoalId, taskId, {
        status: 'completed',
        expected_status: task.status,
        reason: 'Student marked the task complete in the portal',
      });
      setPlan(updated);
      const updatedProgress = await api.rebuildProgress(selectedGoalId);
      setProgress(updatedProgress);
    } catch (requestError) {
      setError(messageFor(requestError));
      throw requestError;
    }
  };

  const selectFocusTask = (task) => {
    const duration = Math.min(Math.max(task?.estimatedMinutes || 25, 5), 120);
    setFocusState({
      task: task || null,
      session: null,
      durationMinutes: duration,
      secondsRemaining: duration * 60,
    });
    setStudentTab('focus');
  };

  const beginFocusSession = async () => {
    if (!selectedGoalId || focusState.session) return focusState.session;
    const started = await api.startFocus({
      goal_id: selectedGoalId,
      task_ref: focusState.task?.id || null,
      milestone_ref: focusState.task?.milestoneId || null,
      objective: focusState.task?.title || 'Independent study session',
      planned_minutes: focusState.durationMinutes,
      idempotency_key: crypto.randomUUID(),
    });
    setFocusState((current) => ({ ...current, session: started }));
    return started;
  };

  const completeFocusSession = async (
    reflection,
    accomplished = true,
    actualMinutesOverride = null,
  ) => {
    if (!focusState.session) return null;
    const elapsedSeconds =
      focusState.durationMinutes * 60 - focusState.secondsRemaining;
    const actualMinutes =
      actualMinutesOverride ?? Math.max(1, Math.ceil(elapsedSeconds / 60));
    const completed = await api.completeFocus(focusState.session.id, {
      expected_version: focusState.session.version,
      actual_minutes: actualMinutes,
      distraction_count: 0,
      blocker_notes: [],
      reflection,
      accomplished,
    });
    setFocusState(emptyFocusState);
    if (selectedGoalId) await loadGoalData(selectedGoalId);
    return completed;
  };

  const addTutorMessage = async (conversationId, text, mode) => {
    if (!selectedGoalId) return;
    setTutorBusy(true);
    setError('');
    const localId = conversationId || crypto.randomUUID();
    const existing = conversations.find((item) => item.id === localId);
    const userMessage = {
      id: crypto.randomUUID(),
      sender: 'student',
      text,
      createdAt: new Date().toISOString(),
    };
    if (existing) {
      setConversations((items) =>
        items.map((item) =>
          item.id === localId
            ? { ...item, messages: [...item.messages, userMessage] }
            : item,
        ),
      );
    } else {
      setConversations((items) => [
        ...items,
        {
          id: localId,
          threadId: null,
          title: text.slice(0, 48),
          mode,
          messages: [userMessage],
        },
      ]);
      setActiveConvId(localId);
    }
    try {
      const response = await api.tutor({
        goal_id: selectedGoalId,
        competency_ref:
          focusState.task?.competencyId ||
          goalGraph?.nodes?.[0]?.competency_id ||
          'general',
        thread_id: existing?.threadId || null,
        mode,
        integrity_mode: 'learning',
        message: text,
      });
      const tutorMessage = {
        id: crypto.randomUUID(),
        sender: 'tutor',
        text: response.response,
        citations: response.citations,
        followUpQuestions: response.follow_up_questions,
        createdAt: new Date().toISOString(),
      };
      setConversations((items) =>
        items.map((item) =>
          item.id === localId
            ? {
                ...item,
                threadId: response.thread_id,
                mode: response.mode,
                messages: [...item.messages, tutorMessage],
              }
            : item,
        ),
      );
    } catch (requestError) {
      setError(messageFor(requestError));
      throw requestError;
    } finally {
      setTutorBusy(false);
    }
  };

  const submitAssessment = async (assessment, answers) => {
    const result = await api.submitAssessment(assessment.id, {
      answers: assessment.questions.map((question) => ({
        question_id: question.id,
        answer: answers[question.id] ?? '',
      })),
      idempotency_key: crypto.randomUUID(),
    });
    if (selectedGoalId) await loadGoalData(selectedGoalId);
    return result;
  };

  const addEvidence = async (payload) => {
    const report = await api.submitEvidence(payload);
    const created = await api.evidenceById(report.evidence_id);
    setEvidence((items) => [
      created,
      ...items.filter((item) => item.id !== created.id),
    ]);
    return report;
  };

  const scanRisks = async () => {
    if (!selectedGoalId) return [];
    const result = await api.scanRisks(selectedGoalId, {});
    setRisks(result.risks);
    return result.risks;
  };

  const requestReplan = async (risk) => {
    if (!selectedGoalId || !plan) return null;
    const proposal = await api.proposeReplan(selectedGoalId, {
      risk_id: risk.id,
      base_plan_ref: plan.id,
      base_plan_version: plan.version,
      preserve_completed_work: true,
      student_constraints: {},
    });
    if (proposal.admin_review_required) return proposal;
    const applied = await api.decideReplan(proposal.id, {
      decision: 'approve',
      expected_version: proposal.version,
      reason: 'Student approved the adaptive replan in the portal',
    });
    await loadGoalData(selectedGoalId);
    return applied;
  };

  const handleReviewAction = async (reviewId, decision, reason) => {
    const decided = await api.decideEvidence(reviewId, {
      decision: decision === 'approve' ? 'verified' : 'rejected',
      reason,
    });
    setReviewItems((items) => items.filter((item) => item.id !== decided.id));
    return decided;
  };

  const verifyAudit = async () => {
    const verification = await api.verifyAudit();
    setOperationsStatus((current) =>
      current
        ? {
            ...current,
            status: verification.valid ? current.status : 'degraded',
            audit: verification,
            components: current.components.map((component) =>
              component.name === 'audit_chain'
                ? {
                    ...component,
                    status: verification.valid ? 'ready' : 'degraded',
                    detail: verification.valid
                      ? `${verification.checked_records} records verified`
                      : verification.reason || 'verification failed',
                  }
                : component,
            ),
          }
        : current,
    );
    return verification;
  };

  const refreshPortal = async () => {
    if (!user) return;
    setBusy(true);
    setError('');
    try {
      await hydrate(user);
      if (user.role === 'student' && selectedGoalId) {
        await loadGoalData(selectedGoalId);
      }
    } catch (requestError) {
      setError(messageFor(requestError));
    } finally {
      setBusy(false);
    }
  };

  const tasks = useMemo(() => {
    const rawTasks = plan?.tasks || [];
    const actions = dailyPlan?.daily_plan || [];
    const actionMap = new Map(actions.map((item) => [item.task_id, item]));
    const visible = actions.length
      ? actions
          .map((action) =>
            rawTasks.find((task) => task.id === action.task_id),
          )
          .filter(Boolean)
      : rawTasks;
    return visible.map((task) => {
      const action = actionMap.get(task.id);
      const category =
        task.priority >= 4
          ? 'Essential'
          : task.priority === 3
            ? 'Recommended'
            : 'Stretch';
      return {
        id: task.id,
        milestoneId: task.milestone_id,
        competencyId: task.competency_id,
        title: task.title,
        description: task.description,
        category,
        competency: task.task_type,
        scheduledTime: action?.starts_at || task.scheduled_start,
        estimatedMinutes: task.estimated_minutes,
        explanation: action?.reason || task.description,
        evidenceDescription: task.evidence_description,
        status: task.status,
      };
    });
  }, [dailyPlan, plan]);

  const selectedGoal = goals.find((goal) => goal.id === selectedGoalId) || null;

  const value = {
    session,
    user,
    appMode,
    setAppMode,
    studentTab,
    setStudentTab,
    adminTab,
    setAdminTab,
    authDialog,
    setAuthDialog,
    authenticate,
    logout,
    booting,
    busy,
    error,
    clearError: () => setError(''),
    refreshPortal,
    studentProfile,
    completeOnboarding,
    goalTemplates,
    goals,
    selectedGoal,
    selectedGoalId,
    setSelectedGoalId,
    goalGraph,
    competencies,
    plan,
    decidePlan,
    regeneratePlan,
    addGoal,
    dailyPlan,
    tasks,
    toggleTaskCompletion,
    progress,
    masteryData,
    risks,
    scanRisks,
    requestReplan,
    assessments,
    submitAssessment,
    evidence,
    addEvidence,
    notifications,
    focusState,
    setFocusState,
    selectFocusTask,
    beginFocusSession,
    completeFocusSession,
    conversations,
    activeConvId,
    setActiveConvId,
    addTutorMessage,
    tutorBusy,
    students,
    agents,
    agentRuns,
    reviewItems,
    handleReviewAction,
    systemHealth,
    operationsStatus,
    securityPolicy,
    verifyAudit,
  };

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
};

export const useApp = () => {
  const context = useContext(AppContext);
  if (!context) throw new Error('useApp must be used within AppProvider');
  return context;
};
