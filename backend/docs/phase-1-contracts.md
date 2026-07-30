# Phase 1 Frozen Contracts

**Contract version:** 1.0  
**API base path:** `/api/v1`  
**Application roles:** `student`, `admin`

These contracts are the compatibility boundary for Phase 2 and the frontend.
Breaking request, response, authorization, or state-machine changes require a new
API version.

## Authentication

| Method | Path | Access | Contract |
|---|---|---|---|
| POST | `/auth/register` | Public, local mode | Creates a `student`; never accepts a role |
| POST | `/auth/login` | Public, local mode | Returns access and refresh tokens |
| POST | `/auth/refresh` | Refresh token | Rotates and revokes the supplied refresh token |
| POST | `/auth/logout` | Authenticated | Revokes the supplied refresh token |
| GET | `/auth/me` | Authenticated | Returns the database-authoritative user |

Access tokens are short-lived bearer JWTs. Refresh tokens are stored only as SHA-256
hashes and rotate on use. Suspending a user increments `auth_version` and revokes all
active refresh sessions. In OIDC mode, the API validates issuer, audience, expiry,
signature, and subject against the configured JWKS endpoint.

Public clients cannot select or create the `admin` role. Admins are bootstrapped by
CLI or provisioned from an explicitly trusted OIDC identity.

## Student profile

| Method | Path | Contract |
|---|---|---|
| POST | `/student/onboarding` | Creates the caller's one profile and version 1 |
| GET | `/student/profile` | Returns only the caller's profile |
| PATCH | `/student/profile` | Requires `expected_version`; writes a new version |
| GET | `/student/profile/completeness` | Deterministic Agent 1 readiness report |

Every update must include `expected_version`. A stale version returns HTTP `409` with
error code `version_conflict` and the current version.

## Goals

| Method | Path | Contract |
|---|---|---|
| POST | `/student/goals` | Creates a caller-owned goal in `draft` |
| GET | `/student/goals` | Lists caller-owned goals with status filter and pagination |
| GET | `/student/goals/{goal_id}` | Returns a caller-owned goal |
| PATCH | `/student/goals/{goal_id}` | Updates an editable goal with optimistic versioning |
| GET | `/student/goals/{goal_id}/versions` | Returns immutable versions newest first |
| POST | `/student/goals/{goal_id}/activate` | `draft -> active` |
| POST | `/student/goals/{goal_id}/pause` | `active -> paused` |
| POST | `/student/goals/{goal_id}/resume` | `paused -> active` |
| POST | `/student/goals/{goal_id}/complete` | `active -> completed` |
| POST | `/student/goals/{goal_id}/close` | `draft/active/paused -> closed` |
| POST | `/student/goals/{goal_id}/clarify` | Runs Agents 1, 2, and 20 through LangGraph |

Activation requires a target date and at least one success criterion. Completed and
closed goals are terminal in Phase 1. Every write creates a `goal_versions` snapshot
and an audit fact in the same database transaction.

## Workflows and agents

| Method | Path | Access |
|---|---|---|
| GET | `/student/workflows/{workflow_id}` | Owning student |
| GET | `/admin/agents` | Admin |

Agent output is schema-validated and can propose state patches, but agents never
write domain tables directly. Agent runs persist identity, version, policy version,
idempotency key, input/output hashes, route, and result.

Registered Phase 1 agents:

- `StudentProfileAgent` (`agent-01`)
- `GoalClarificationAgent` (`agent-02`)
- `SupervisorGovernanceAgent` (`agent-20`)

## Admin

| Method | Path | Contract |
|---|---|---|
| GET | `/admin/users` | Paginated users with role/status filters |
| GET | `/admin/users/{user_id}` | User operational view |
| PATCH | `/admin/users/{user_id}/status` | Suspend or reactivate; self-change forbidden |
| GET | `/admin/audit` | Filtered immutable audit history |
| GET | `/admin/agents` | Registered agent contracts |

Admin reads are themselves audited. Admins cannot delete audit facts or silently
edit a student's profile or goal through Phase 1 APIs.

## Audit

Audit records are append-only at the ORM boundary and protected by a PostgreSQL
trigger. Each record includes actor, action, resource, student scope, request and
correlation identifiers, before/after state, metadata, previous hash, and event hash.

The event hash forms a tamper-evident chain. Audit payloads never contain passwords
or raw refresh/access tokens.

## Error shape

All known API errors use:

```json
{
  "error": {
    "code": "version_conflict",
    "message": "Goal was updated by another request",
    "details": {"current_version": 2},
    "request_id": "2b1f5e57-796b-47d3-99b7-5905b41139cb"
  }
}
```

Stable status behavior:

- `401`: missing, invalid, expired, revoked, or superseded credentials
- `403`: valid identity without role, ownership, or account permission
- `404`: resource absent or hidden by ownership scope
- `409`: uniqueness, lifecycle, or optimistic-version conflict
- `422`: schema validation failure

