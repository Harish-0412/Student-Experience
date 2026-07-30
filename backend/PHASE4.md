# AstraPath Phase 4 Backend

Phase 4 implements the adaptive learning and intelligence loop. It turns a
student's goal into measurable learning activity through curated resources,
focus sessions, grounded tutoring, assessments, evidence verification,
four-dimensional progress, mastery estimates, coaching, risk detection, and
approval-based replanning.

Only two application roles exist: `student` and `admin`.

## Phase 3 Integration Contract

Phase 4 keeps a narrow persistence boundary while running inside the main
Phase 1-4 application:

- No Phase 3 table has a foreign key from a Phase 4 table.
- `plan_ref`, `task_ref`, and `milestone_ref` are opaque strings.
- Phase 3 publishes plan, task, milestone, schedule, and adherence snapshots
  through `Phase3Phase4Bridge`.
- Phase 4 produces typed minimal plan operations; Phase 3 validates, schedules,
  versions, and applies them.
- Approved replans record the resulting Phase 3 plan reference and version
  before becoming `applied`.
- Completed and dropped work is preserved across plan versions.

The package depends only on the frozen Phase 1 `users`, `goals`, authentication,
authorization, error, and append-only audit contracts.

## Architecture

```text
HTTP API
  -> Phase4Service (authorization, ownership, transactions, audit)
    -> AgentRunner (typed output, idempotency, provenance)
      -> deterministic Phase 4 agents
    -> SQLAlchemy repositories/models
      -> progress events and immutable versioned snapshots
  <-> Phase3Phase4Bridge
      -> PlanningService (validated plan version and constrained schedule)
```

The implementation lives in `src/astrapath/phase4`:

- `contracts.py`: strict Pydantic request, response, and agent contracts.
- `models.py`: 19 Phase 4 persistence models.
- `agents/`: bounded agents with typed output and explicit tool allowlists.
- `registry.py`: agent discovery, provenance, execution, and replay control.
- `service.py`: workflows, ownership checks, optimistic concurrency, and audit.
- `api.py`: 33 student/admin operations under `/api/v1`.
- `phase3_bridge.py`: execution-context publication and approved replan apply.
- `schema.py`: isolated schema bootstrap without Phase 3 tables.
- `standalone.py`: development and contract-test application.

## Agent Contract

Ten agents are registered:

| Agent | Responsibility |
| --- | --- |
| `ResourceCurationAgent` | Rank approved resources against learner constraints |
| `FocusSessionCoachAgent` | Start and complete bounded study sessions |
| `ContextualTutorAgent` | Answer from approved sources with citations |
| `AssessmentGenerationAgent` | Generate and deterministically score assessments |
| `EvidenceVerificationAgent` | Validate trusted artifacts and acceptance criteria |
| `ProgressTrackingAgent` | Compute activity, milestone, mastery, and confidence |
| `MasteryEstimationAgent` | Produce calibrated competency estimates |
| `MotivationHabitCoachAgent` | Provide bounded, non-clinical coaching |
| `RiskBlockerDetectionAgent` | Detect deadline, overload, stagnation, and blockers |
| `AdaptiveReplanningAgent` | Produce minimal plan diffs for human approval |

Each run records the agent and prompt versions, model route, policy version,
input/output hashes, status, actor, student, goal, and timestamps. Reusing an
idempotency key with different input is rejected.

## Core Workflows

### Resource and Tutor

1. Admin creates and reviews a resource.
2. Student receives only approved, constraint-matched resources.
3. Tutor retrieves approved excerpts and returns citations.
4. Graded mode refuses submission-ready answers and shifts to guided reasoning.

### Focus, Assessment, and Mastery

1. Student starts one idempotent focus session.
2. Completion records time, outcome, distractions, and blockers.
3. Admin creates or generates an assessment and publishes it.
4. Student answers are scored without exposing answer keys.
5. Assessment and evidence signals rebuild competency mastery and progress.

### Evidence

1. Admin registers an object-store receipt and scanner result.
2. Student submits metadata, checksum, extracted content, and criteria.
3. Trusted content is evaluated deterministically.
4. Untrusted, quarantined, executable, or unparseable content requires admin
   review.
5. Only verified evidence contributes to mastery and progress.

### Risk and Replanning

1. Progress and execution context are evaluated for deterministic risks.
2. A minimal plan patch preserves completed work.
3. Critical or technical changes require admin review.
4. Student approval changes the state to `approved_pending_phase3`.
5. The bridge asks Phase 3 to validate, schedule, version, and approve the diff.
6. Phase 4 records the applied plan and updates the execution context.

## Safety and Data Invariants

- Goal ownership is checked for every student workflow.
- Admin-only mutations are checked in the service, not only at the route layer.
- Focus, assessment, evidence, and agent operations are replay-safe.
- Moderated records use version checks or row locks.
- Evidence checks storage checksum, size, media type, and scanner status.
- Evidence cannot reference another student's assessment attempt.
- Progress and mastery are versioned snapshots derived from persisted signals.
- Audit events are written for mutations and intelligence decisions.
- Resource answer sources and tutor citations are restricted to approved data.

## Running the Integrated Application

```powershell
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m uvicorn astrapath.main:app --port 8000
```

The Phase 4 migration is `be21515c6e1c` and follows the final Phase 3 revision.
The main application uses normal Phase 1 bearer authentication and exactly the
`student` and `admin` roles.

## Standalone Contract Tests

```powershell
$env:PYTHONPATH = "src"
.venv\Scripts\python.exe -m uvicorn `
  astrapath.phase4.standalone:create_phase4_app `
  --factory --port 8004
```

The standalone boundary accepts `X-AstraPath-Actor-Id` and
`X-AstraPath-Actor-Role` headers for local development only. The actor IDs must
exist in its database when audited mutations are performed.

Run the Phase 4 checks with:

```powershell
.venv\Scripts\ruff.exe check --no-cache src\astrapath\phase4 tests\phase4
.venv\Scripts\mypy.exe src\astrapath\phase4
.venv\Scripts\python.exe -m pytest tests\phase4 -q -p no:cacheprovider
```

The standalone app remains available to test Phase 4 contracts without Phase 3.
In that boundary, approved replans stop at `approved_pending_phase3` because no
planning service is present.
