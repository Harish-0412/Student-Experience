# AstraPath Backend

The backend implements AstraPath Phases 1 through 5 with exactly two
application roles: `student` and `admin`.

## Included

- FastAPI application and versioned `/api/v1` contracts
- Local JWT authentication with rotating, revocable refresh tokens
- Production OIDC bearer-token validation through a configured JWKS endpoint
- Student/Admin role-based authorization and ownership enforcement
- Versioned student profiles and onboarding
- Versioned goals with validated lifecycle transitions
- Append-only, hash-chained audit records
- Goal clarification, feasibility, skill-gap, and competency graph generation
- Milestones, tasks, constrained scheduling, calendar views, and daily plans
- Explainable decision cards and student plan approval/edit/rejection
- Resource curation, focus sessions, contextual tutoring, and assessments
- Evidence verification, progress snapshots, mastery estimates, and coaching
- Risk detection and approval-based adaptive replanning
- Transactional Phase 3/Phase 4 execution-context and replan bridge
- Phase 5 request hardening, rate limits, admission control, metrics, and audit verification
- Typed contracts and registry for Agents 1, 2, 3, 4, 5, 6, 8, 9, and 20
- Typed contracts and registry for ten Phase 4 learning and adaptation agents
- LangGraph goal-clarification workflow
- Temporal workflow and worker proof of concept
- PostgreSQL migrations and SQLite-compatible tests

## Local setup

```powershell
cd C:\SideQuest\Students\backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
Copy-Item .env.example .env
docker compose up -d postgres temporal temporal-ui
.\.venv\Scripts\alembic.exe upgrade head
.\.venv\Scripts\uvicorn.exe astrapath.main:app --reload
```

API documentation is available at `http://127.0.0.1:8000/docs`. Temporal UI is
available at `http://127.0.0.1:8088`.

For a lightweight local run without Docker, set:

```text
ASTRAPATH_DATABASE_URL=sqlite:///./astrapath.db
```

Then run the migration and API commands normally.

## Bootstrap the first admin

Public registration can create students only. Create the first local admin after
running migrations:

```powershell
.\.venv\Scripts\astrapath-admin.exe --email admin@example.com --name "Platform Admin"
```

For OIDC, provide `--oidc-issuer` and `--oidc-subject`. Admin creation is deliberately
outside the public HTTP API.

## Quality checks

```powershell
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\pytest.exe
.\.venv\Scripts\mypy.exe src
```

## Contracts

The frozen Phase 1 behavior is documented in
[`docs/phase-1-contracts.md`](docs/phase-1-contracts.md). Database changes must be
made through Alembic, and breaking API changes require a new API version.

Phase-specific contracts and integration notes are documented in
[`PHASE2.md`](PHASE2.md), [`PHASE3.md`](PHASE3.md),
[`PHASE4.md`](PHASE4.md), and [`PHASE5.md`](PHASE5.md).

## Operational checks

The Phase 5 operational API is Admin-only:

```text
GET  /api/v1/admin/operations/status
GET  /api/v1/admin/operations/metrics
GET  /api/v1/admin/operations/security-policy
POST /api/v1/admin/operations/audit/verify
```

Run a load check against a running API:

```powershell
.\.venv\Scripts\astrapath-load.exe --requests 1000 --concurrency 50
```
