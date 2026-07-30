# AstraPath Phase 2 Backend

This package implements goal clarification, feasibility analysis, skill-gap
analysis, competency profiles, PostgreSQL-compatible learning graphs, goal
templates, success criteria, and decision cards.

## Phase 1 Integration

Phase 2 is wired into the main AstraPath application. Its routes use the
Phase 1 bearer-token principal, ownership policy, database session, request
context, and append-only audit service. Agents 3, 4, and 5 are registered in
the shared Agent Registry, and Alembic loads the Phase 2 metadata.

The standalone app is for Phase 2 development only:

```powershell
$env:PYTHONPATH = "src"
uvicorn astrapath.phase2.standalone:create_phase2_app --factory
```

It exposes the required API under `/api/v1`. Its development-only actor headers
are overridden only inside the standalone factory and are not available in the
integrated application.

## Workflow

The API enforces:

```text
clarify -> feasibility -> skill-gap + graph generation -> graph reads
```

`POST /skill-gap` creates the competency graph because Phase 2 defines graph
retrieval but no separate graph-generation POST endpoint.

The default catalog validates three representative student goals:

- Machine learning internship readiness
- Data structures interview preparation
- Calculus exam preparation

Admin-created templates are checked for unknown competencies, missing
prerequisites, duplicate requirements, and prerequisite cycles.
