from collections.abc import Iterator

from fastapi import FastAPI
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from astrapath.audit import AuditService
from astrapath.db import build_engine, get_db
from astrapath.dependencies import get_current_user
from astrapath.errors import register_exception_handlers
from astrapath.phase4.api import phase4_router
from astrapath.phase4.integration import get_standalone_phase4_actor
from astrapath.phase4.registry import build_phase4_registry
from astrapath.phase4.schema import create_phase4_standalone_schema


def create_phase4_app(database_url: str = "sqlite:///:memory:") -> FastAPI:
    """Create the isolated Phase 4 app without importing or wiring Phase 3."""
    engine_kwargs = (
        {"poolclass": StaticPool} if database_url == "sqlite:///:memory:" else {}
    )
    engine = build_engine(database_url, **engine_kwargs)
    create_phase4_standalone_schema(engine)
    session_factory = sessionmaker(
        bind=engine, autoflush=False, expire_on_commit=False
    )

    def phase4_db() -> Iterator[Session]:
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app = FastAPI(
        title="AstraPath Phase 4 Adaptive Learning",
        version="4.0.0",
    )
    register_exception_handlers(app)
    app.state.audit_service = AuditService()
    app.state.phase4_registry = build_phase4_registry()
    app.include_router(phase4_router)
    app.dependency_overrides[get_db] = phase4_db
    app.dependency_overrides[get_current_user] = get_standalone_phase4_actor
    app.state.engine = engine
    app.state.session_factory = session_factory
    return app
