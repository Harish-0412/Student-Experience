from collections.abc import Iterator

from fastapi import FastAPI
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from astrapath.audit import AuditService
from astrapath.db import Base, build_engine, get_db
from astrapath.dependencies import get_current_user
from astrapath.errors import register_exception_handlers
from astrapath.phase2.api import phase2_router
from astrapath.phase2.integration import get_standalone_phase2_actor


def create_phase2_app(database_url: str = "sqlite:///:memory:") -> FastAPI:
    """Create an isolated Phase 2 app for development and contract testing."""

    engine_kwargs = (
        {"poolclass": StaticPool} if database_url == "sqlite:///:memory:" else {}
    )
    engine = build_engine(database_url, **engine_kwargs)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(
        bind=engine, autoflush=False, expire_on_commit=False
    )

    def phase2_db() -> Iterator[Session]:
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app = FastAPI(
        title="AstraPath Phase 2 Goal Intelligence",
        version="2.0.0",
    )
    register_exception_handlers(app)
    app.state.audit_service = AuditService()
    app.include_router(phase2_router)
    app.dependency_overrides[get_db] = phase2_db
    app.dependency_overrides[get_current_user] = get_standalone_phase2_actor
    app.state.engine = engine
    app.state.session_factory = session_factory
    return app
