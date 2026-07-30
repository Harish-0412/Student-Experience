from astrapath.db import Base
from astrapath.phase4.schema import PHASE4_TABLE_NAMES
from tests.phase4.conftest import headers


def test_phase4_schema_has_no_phase3_foreign_keys() -> None:
    allowed_tables = {*PHASE4_TABLE_NAMES, "users", "goals"}
    referenced_tables = {
        foreign_key.column.table.name
        for table_name in PHASE4_TABLE_NAMES
        for foreign_key in Base.metadata.tables[table_name].foreign_keys
    }
    assert referenced_tables <= allowed_tables
    assert not referenced_tables & {"plans", "tasks", "milestones"}


def test_openapi_and_agent_contracts_are_exposed(phase4_env: dict) -> None:
    client = phase4_env["client"]
    ids = phase4_env["ids"]
    schema = client.get("/openapi.json").json()

    assert len(schema["paths"]) == 32
    assert "get" in schema["paths"]["/api/v1/student/evidence"]
    assert "/api/v1/student/tutor/messages" in schema["paths"]
    assert "/api/v1/admin/phase4/evidence/{evidence_id}/decision" in schema["paths"]
    assert "/api/v1/admin/phase4/goals/{goal_id}/execution-context" in schema["paths"]

    invalid_role = client.get(
        "/api/v1/admin/phase4/agents",
        headers=headers(ids["admin"], "teacher"),
    )
    assert invalid_role.status_code == 403
    assert invalid_role.json()["error"]["code"] == "invalid_role"
