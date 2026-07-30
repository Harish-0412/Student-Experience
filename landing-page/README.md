# AstraPath Frontend

Vite/React portal for the integrated AstraPath Phase 1-5 backend. The UI
supports exactly two authenticated roles: `student` and `admin`.

## Connected Workflows

- Student registration, sign-in, refresh, sign-out, and onboarding
- Goal clarification, feasibility, skill-gap analysis, and plan generation
- Plan approval, daily actions, task completion, and focus sessions
- Contextual tutoring, assessments, evidence, progress, mastery, and risks
- Adaptive replanning through the Phase 3/Phase 4 bridge
- Admin users, agent descriptors/runs, evidence review, and Phase 5 operations

All portal records come from the API. No mock dataset is included.

## Local Run

Start the migrated backend on `http://localhost:8000`, then:

```powershell
cd C:\SideQuest\Students\landing-page
npm.cmd install
npm.cmd run dev
```

The portal is available at `http://localhost:5173`.

Set `VITE_API_URL` when the backend is hosted elsewhere:

```text
VITE_API_URL=http://localhost:8000/api/v1
```

## Checks

```powershell
npm.cmd run lint
npm.cmd run build
```
