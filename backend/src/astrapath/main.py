from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from astrapath import __version__
from astrapath.agents.kernel import (
    GoalClarificationAgent,
    StudentProfileAgent,
    SupervisorGovernanceAgent,
)
from astrapath.agents.registry import AgentRegistry
from astrapath.agents.supervisor import Supervisor
from astrapath.api.router import api_router
from astrapath.audit import AuditService
from astrapath.config import Settings, get_settings
from astrapath.errors import register_exception_handlers
from astrapath.phase2.agents import (
    GoalFeasibilityAgent,
    LearningPathArchitectAgent,
    SkillGapAnalysisAgent,
)
from astrapath.phase2.api import phase2_router
from astrapath.phase3.agents import (
    DailyActionPlanningAgent,
    MilestoneDecompositionAgent,
    ScheduleTimeBudgetAgent,
)
from astrapath.phase3.api import phase3_router
from astrapath.phase3.service import PlanningService
from astrapath.phase4.api import phase4_router
from astrapath.phase4.phase3_bridge import Phase3Phase4Bridge
from astrapath.phase4.registry import build_phase4_registry
from astrapath.phase5.api import phase5_router
from astrapath.phase5.metrics import MetricsRegistry
from astrapath.phase5.middleware import (
    AdmissionController,
    IdempotencyStore,
    OperationalMiddleware,
    SlidingWindowRateLimiter,
)
from astrapath.phase5.service import OperationalService
from astrapath.security import TokenService
from astrapath.services import AdminService, AuthService, GoalService, ProfileService


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        yield

    app = FastAPI(
        title=resolved_settings.app_name,
        version=__version__,
        description=(
            "AstraPath Phase 1-5 API. Contracts are versioned under /api/v1 "
            "and support exactly two roles: student and admin."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "X-Request-ID",
            "X-Correlation-ID",
            "X-Access-Reason",
            "Idempotency-Key",
        ],
    )
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=resolved_settings.trusted_hosts,
    )

    metrics_registry = MetricsRegistry()
    rate_limiter = SlidingWindowRateLimiter(
        resolved_settings.rate_limit_window_seconds
    )
    admission = AdmissionController(resolved_settings.max_inflight_requests)
    idempotency = IdempotencyStore(
        ttl_seconds=resolved_settings.idempotency_ttl_seconds,
        max_entries=resolved_settings.idempotency_max_entries,
    )
    app.add_middleware(
        OperationalMiddleware,
        settings=resolved_settings,
        metrics=metrics_registry,
        rate_limiter=rate_limiter,
        admission=admission,
        idempotency=idempotency,
    )

    audit_service = AuditService()
    token_service = TokenService(resolved_settings)
    registry = AgentRegistry(
        [
            StudentProfileAgent(),
            GoalClarificationAgent(),
            GoalFeasibilityAgent(),
            SkillGapAnalysisAgent(),
            LearningPathArchitectAgent(),
            MilestoneDecompositionAgent(),
            ScheduleTimeBudgetAgent(),
            DailyActionPlanningAgent(),
            SupervisorGovernanceAgent(),
        ]
    )
    app.state.settings = resolved_settings
    app.state.token_service = token_service
    app.state.audit_service = audit_service
    app.state.auth_service = AuthService(resolved_settings, token_service, audit_service)
    app.state.profile_service = ProfileService(audit_service)
    app.state.goal_service = GoalService(audit_service)
    app.state.admin_service = AdminService(audit_service)
    app.state.agent_registry = registry
    app.state.supervisor = Supervisor(registry, audit_service)
    planning_service = PlanningService(audit_service, app.state.supervisor)
    phase4_registry = build_phase4_registry()
    phase3_phase4_bridge = Phase3Phase4Bridge(
        audit_service,
        planning_service,
    )
    planning_service.execution_sink = phase3_phase4_bridge
    app.state.planning_service = planning_service
    app.state.phase4_registry = phase4_registry
    app.state.phase3_phase4_bridge = phase3_phase4_bridge
    app.state.metrics_registry = metrics_registry
    app.state.operational_service = OperationalService(metrics_registry)

    register_exception_handlers(app)
    app.include_router(api_router, prefix=resolved_settings.api_prefix)
    app.include_router(phase2_router)
    app.include_router(phase3_router)
    app.include_router(phase4_router)
    app.include_router(phase5_router)
    return app


app = create_app()
