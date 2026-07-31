from sqlalchemy.engine import Engine

from astrapath.db import Base

PHASE4_TABLE_NAMES = (
    "phase4_execution_contexts",
    "learning_resources",
    "resource_recommendations",
    "focus_sessions",
    "tutor_threads",
    "tutor_messages",
    "assessment_definitions",
    "assessment_attempts",
    "phase4_storage_receipts",
    "evidence_submissions",
    "evidence_reviews",
    "progress_events",
    "progress_snapshots",
    "mastery_estimates",
    "coaching_records",
    "risks",
    "replan_proposals",
    "notifications",
    "phase4_agent_runs",
)

STANDALONE_SHARED_TABLE_NAMES = (
    "users",
    "goals",
    "audit_chain_heads",
    "audit_logs",
)


def create_phase4_schema(engine: Engine) -> None:
    """Create only Phase 4 tables after the shared users/goals schema exists."""
    tables = [Base.metadata.tables[name] for name in PHASE4_TABLE_NAMES]
    Base.metadata.create_all(engine, tables=tables)


def create_phase4_standalone_schema(engine: Engine) -> None:
    """Create the minimal Phase 1 dependencies plus Phase 4 tables."""
    names = (*STANDALONE_SHARED_TABLE_NAMES, *PHASE4_TABLE_NAMES)
    tables = [Base.metadata.tables[name] for name in names]
    Base.metadata.create_all(engine, tables=tables)
