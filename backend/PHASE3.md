# AstraPath Phase 3 Backend

Phase 3 converts the Phase 2 learning graph into an evidence-backed plan that
fits the student's actual availability.

## Included

- Agent 6: Milestone Decomposition Agent
- Agent 8: Schedule and Time-Budget Agent
- Agent 9: Daily Action Planning Agent
- Deterministic effort estimation
- Milestones with acceptance criteria, evidence, dependencies, dates, and buffer
- Learning, practice, application, and review tasks
- Weekly capacity, session, break, daily-load, and buffer constraints
- Fixed commitment and do-not-disturb protection
- Cross-goal schedule conflict detection without calendar overwrite
- Calendar and daily-plan read models
- Student task editing, schedule regeneration, approval, and rejection
- Optimistic task execution status updates
- Versioned Phase 4 execution-context publication
- Validated application of approved adaptive replan operations
- Decision cards and append-only audit events

The primary platform blueprint assigns resource curation to Phase 4, so Phase 3
does not implement resource search, Qdrant, or tutor behavior.

## API

```text
POST  /api/v1/goals/{goal_id}/plan
GET   /api/v1/goals/{goal_id}/plan
POST  /api/v1/goals/{goal_id}/schedule
PATCH /api/v1/goals/{goal_id}/plan/tasks/{task_id}
PATCH /api/v1/goals/{goal_id}/plan/tasks/{task_id}/status
POST  /api/v1/goals/{goal_id}/plan/decision
GET   /api/v1/goals/{goal_id}/calendar
GET   /api/v1/student/daily-plan
```

Plan generation requires a completed Phase 2 competency graph. Generated plans
remain `proposed` until the student approves them. Plans with blocking schedule
conflicts cannot be approved.

## Scheduling Rules

The scheduler:

- Uses only declared weekly availability.
- Enforces weekly and daily learning limits.
- Splits work into bounded sessions with minimum breaks.
- Reserves configurable catch-up capacity.
- Protects fixed commitments and do-not-disturb windows.
- Treats proposed and approved blocks from other goals as unavailable.
- Preserves prerequisite task ordering.
- Returns deadline and cross-goal conflicts with explainable alternatives.

No external calendar is written in Phase 3. Calendar integration remains an
explicit future boundary and must require student confirmation.

## Phase 4 Bridge

Phase 3 owns plan mutation. It publishes execution snapshots through a narrow
sink contract and accepts only typed, already-approved Phase 4 replan commands.
Each command creates a new plan version, preserves completed work, runs the
constraint scheduler, rejects blocking conflicts, supersedes the previous plan,
and records audit provenance.
