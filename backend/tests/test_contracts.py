from fastapi.testclient import TestClient

from astrapath.enums import Role


def test_role_contract_has_exactly_two_values() -> None:
    assert {role.value for role in Role} == {"student", "admin"}


def test_openapi_contains_frozen_phase_one_paths(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    paths = schema["paths"]
    required_paths = {
        "/api/v1/auth/register",
        "/api/v1/auth/login",
        "/api/v1/auth/refresh",
        "/api/v1/auth/me",
        "/api/v1/student/onboarding",
        "/api/v1/student/profile",
        "/api/v1/student/goals",
        "/api/v1/student/goals/{goal_id}",
        "/api/v1/student/goals/{goal_id}/clarify",
        "/api/v1/admin/users",
        "/api/v1/admin/audit",
        "/api/v1/admin/agents",
    }
    assert required_paths <= set(paths)
    register_properties = schema["components"]["schemas"]["RegisterRequest"]["properties"]
    assert "role" not in register_properties
