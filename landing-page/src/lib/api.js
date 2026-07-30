const API_BASE_URL = (
  import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1'
).replace(/\/$/, '');

const SESSION_KEY = 'astrapath.session';

export class ApiError extends Error {
  constructor(status, code, message, details = null) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

export const readSession = () => {
  try {
    return JSON.parse(sessionStorage.getItem(SESSION_KEY)) || null;
  } catch {
    sessionStorage.removeItem(SESSION_KEY);
    return null;
  }
};

export const writeSession = (session) => {
  if (session) {
    sessionStorage.setItem(SESSION_KEY, JSON.stringify(session));
  } else {
    sessionStorage.removeItem(SESSION_KEY);
  }
};

const parseResponse = async (response) => {
  if (response.status === 204) return null;
  const contentType = response.headers.get('content-type') || '';
  return contentType.includes('application/json')
    ? response.json()
    : response.text();
};

const refreshAccessToken = async () => {
  const current = readSession();
  if (!current?.refresh_token) return null;
  const response = await fetch(`${API_BASE_URL}/auth/refresh`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: current.refresh_token }),
  });
  if (!response.ok) {
    writeSession(null);
    return null;
  }
  const session = await response.json();
  writeSession(session);
  return session;
};

export const request = async (
  path,
  { method = 'GET', body, query, auth = true, retry = true } = {},
) => {
  const url = new URL(`${API_BASE_URL}${path}`);
  Object.entries(query || {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') {
      url.searchParams.set(key, String(value));
    }
  });

  const session = readSession();
  const headers = { Accept: 'application/json' };
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  if (auth && session?.access_token) {
    headers.Authorization = `Bearer ${session.access_token}`;
  }

  const response = await fetch(url, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });

  if (response.status === 401 && auth && retry) {
    const refreshed = await refreshAccessToken();
    if (refreshed) {
      return request(path, { method, body, query, auth, retry: false });
    }
  }

  const payload = await parseResponse(response);
  if (!response.ok) {
    const error = payload?.error || {};
    throw new ApiError(
      response.status,
      error.code || 'request_failed',
      error.message || `Request failed with status ${response.status}`,
      error.details || null,
    );
  }
  return payload;
};

export const api = {
  register: (payload) =>
    request('/auth/register', { method: 'POST', body: payload, auth: false }),
  login: (payload) =>
    request('/auth/login', { method: 'POST', body: payload, auth: false }),
  me: () => request('/auth/me'),
  logout: (refreshToken) =>
    request('/auth/logout', {
      method: 'POST',
      body: { refresh_token: refreshToken },
    }),

  profile: () => request('/student/profile'),
  onboard: (payload) =>
    request('/student/onboarding', { method: 'POST', body: payload }),
  updateProfile: (payload) =>
    request('/student/profile', { method: 'PATCH', body: payload }),

  goals: async () => (await request('/student/goals')).items,
  createGoal: (payload) =>
    request('/student/goals', { method: 'POST', body: payload }),
  clarifyGoal: (goalId, payload) =>
    request(`/goals/${goalId}/clarify`, { method: 'POST', body: payload }),
  assessFeasibility: (goalId, payload) =>
    request(`/goals/${goalId}/feasibility`, { method: 'POST', body: payload }),
  analyzeSkillGap: (goalId, payload = {}) =>
    request(`/goals/${goalId}/skill-gap`, { method: 'POST', body: payload }),
  graph: (goalId) => request(`/goals/${goalId}/graph`),
  competencies: (goalId) => request(`/goals/${goalId}/competencies`),

  plan: (goalId) => request(`/goals/${goalId}/plan`),
  generatePlan: (goalId, payload = {}) =>
    request(`/goals/${goalId}/plan`, { method: 'POST', body: payload }),
  decidePlan: (goalId, payload) =>
    request(`/goals/${goalId}/plan/decision`, {
      method: 'POST',
      body: payload,
    }),
  updateTaskStatus: (goalId, taskId, payload) =>
    request(`/goals/${goalId}/plan/tasks/${taskId}/status`, {
      method: 'PATCH',
      body: payload,
    }),
  dailyPlan: (date) => request('/student/daily-plan', { query: { date } }),

  startFocus: (payload) =>
    request('/student/focus-sessions', { method: 'POST', body: payload }),
  completeFocus: (sessionId, payload) =>
    request(`/student/focus-sessions/${sessionId}/complete`, {
      method: 'POST',
      body: payload,
    }),
  tutor: (payload) =>
    request('/student/tutor/messages', { method: 'POST', body: payload }),

  assessments: (goalId) =>
    request(`/student/goals/${goalId}/assessments`),
  submitAssessment: (assessmentId, payload) =>
    request(`/student/assessments/${assessmentId}/attempts`, {
      method: 'POST',
      body: payload,
    }),

  evidence: (goalId) =>
    request('/student/evidence', { query: { goal_id: goalId } }),
  submitEvidence: (payload) =>
    request('/student/evidence', { method: 'POST', body: payload }),
  evidenceById: (evidenceId) =>
    request(`/student/evidence/${evidenceId}`),

  progress: (goalId) => request(`/student/goals/${goalId}/progress`),
  rebuildProgress: (goalId) =>
    request(`/student/goals/${goalId}/progress/rebuild`, { method: 'POST' }),
  mastery: (goalId) => request(`/student/goals/${goalId}/mastery`),
  risks: (goalId) => request(`/student/goals/${goalId}/risks`),
  scanRisks: (goalId, payload = {}) =>
    request(`/student/goals/${goalId}/risks/scan`, {
      method: 'POST',
      body: payload,
    }),
  proposeReplan: (goalId, payload) =>
    request(`/student/goals/${goalId}/replans`, {
      method: 'POST',
      body: payload,
    }),
  decideReplan: (proposalId, payload) =>
    request(`/student/replans/${proposalId}/decision`, {
      method: 'POST',
      body: payload,
    }),
  notifications: () => request('/student/notifications'),

  users: () => request('/admin/users'),
  phase123Agents: () => request('/admin/agents'),
  phase4Agents: () => request('/admin/phase4/agents'),
  agentRuns: () => request('/admin/phase4/agent-runs'),
  reviewQueue: () => request('/admin/phase4/evidence/review-queue'),
  decideEvidence: (evidenceId, payload) =>
    request(`/admin/phase4/evidence/${evidenceId}/decision`, {
      method: 'POST',
      body: payload,
    }),
  operationsStatus: () => request('/admin/operations/status'),
  operationsMetrics: () => request('/admin/operations/metrics'),
  securityPolicy: () => request('/admin/operations/security-policy'),
  verifyAudit: () =>
    request('/admin/operations/audit/verify', { method: 'POST' }),
  health: () => request('/health/ready', { auth: false }),
};

export { API_BASE_URL };
