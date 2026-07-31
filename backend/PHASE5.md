# AstraPath Phase 5 Backend

Phase 5 hardens the integrated Phase 1-4 application for production operation.
It adds no application role: authorization remains exactly `student` and
`admin`.

## Included

- Trusted-host and production transport checks
- Request-size limits and security response headers
- Separate authentication and general sliding-window rate limits
- Bounded in-flight request admission
- HTTP `Idempotency-Key` replay protection for authenticated mutations
- Authentication responses explicitly excluded from replay caching
- Sanitized unexpected-error responses
- Request, response, rejection, replay, and latency metrics
- Operational status across database, audit chain, agent registries, and bridge
- Full append-only audit-chain verification
- Transactional audit-head reservation for concurrent hash-chain writes
- Load and resilience validation helpers

## Admin API

```text
GET  /api/v1/admin/operations/status
GET  /api/v1/admin/operations/metrics
GET  /api/v1/admin/operations/security-policy
POST /api/v1/admin/operations/audit/verify
```

All operations endpoints require an `admin` bearer token. Metrics are
process-local and deliberately contain no student content or credentials.

## Configuration

The request guard is controlled by `ASTRAPATH_TRUSTED_HOSTS`,
`ASTRAPATH_TRUST_PROXY_HEADERS`, `ASTRAPATH_MAX_REQUEST_BYTES`, and the
rate-limit, admission, and idempotency settings listed in `.env.example`.
Wildcard CORS origins and trusted hosts are rejected in staging and production.
Forwarded client IP headers are ignored unless explicitly enabled behind a
trusted ingress.

## Verification

```powershell
.venv\Scripts\python.exe -m pytest tests\phase5 -q -p no:cacheprovider
.venv\Scripts\astrapath-load.exe --requests 1000 --concurrency 50
```

The Phase 5 end-to-end test covers authentication, Phase 2 intelligence,
Phase 3 planning and task execution, Phase 4 progress/risk/replanning, and
Phase 5 operational readiness in one journey.

The Phase 5 audit-head migration serializes hash reservations inside the same
database transaction as each audited operation. The limiter, response replay
cache, metrics, and circuit state are bounded per API process. Multi-replica
production deployments should move shared rate-limit and idempotency state to
Redis and export metrics and traces to the configured observability stack.
