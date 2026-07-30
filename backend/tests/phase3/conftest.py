from datetime import date, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.conftest import bearer, register_student


@pytest.fixture
def planning_student(client: TestClient) -> dict[str, Any]:
    token_pair = register_student(
        client,
        email="planner@example.com",
        name="Planning Student",
    )
    headers = bearer(token_pair["access_token"])
    onboarding = client.post(
        "/api/v1/student/onboarding",
        headers=headers,
        json={
            "display_name": "Planning Student",
            "timezone": "Asia/Kolkata",
            "locale": "en-IN",
            "education_level": "Undergraduate",
            "institution": "Example University",
            "weekly_learning_minutes": 600,
            "learning_preferences": ["project-based"],
            "availability": {
                weekday: [
                    {"start": "18:00", "end": "20:00", "energy": "high"}
                ]
                for weekday in [
                    "monday",
                    "tuesday",
                    "wednesday",
                    "thursday",
                    "friday",
                ]
            },
            "device_access": ["laptop"],
            "accessibility_needs": [],
            "consent_scopes": [],
            "onboarding_completed": True,
        },
    )
    assert onboarding.status_code == 201, onboarding.text
    return {
        "headers": headers,
        "user": token_pair["user"],
    }


def create_goal(
    client: TestClient,
    headers: dict[str, str],
    *,
    title: str,
    raw_statement: str,
    weeks: int,
) -> dict[str, Any]:
    response = client.post(
        "/api/v1/student/goals",
        headers=headers,
        json={
            "title": title,
            "raw_statement": raw_statement,
            "target_date": (date.today() + timedelta(weeks=weeks)).isoformat(),
            "priority": 4,
            "success_criteria": [],
            "assumptions": [],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def complete_phase2(
    client: TestClient,
    headers: dict[str, str],
    goal_id: str,
    *,
    template_slug: str,
    weekly_hours: float,
    evidence: list[dict[str, Any]],
) -> dict[str, Any]:
    clarification = client.post(
        f"/api/v1/goals/{goal_id}/clarify",
        headers=headers,
        json={
            "template_slug": template_slug,
            "weekly_hours": weekly_hours,
        },
    )
    assert clarification.status_code == 200, clarification.text
    feasibility = client.post(
        f"/api/v1/goals/{goal_id}/feasibility",
        headers=headers,
        json={"weekly_hours": weekly_hours},
    )
    assert feasibility.status_code == 200, feasibility.text
    skill_gap = client.post(
        f"/api/v1/goals/{goal_id}/skill-gap",
        headers=headers,
        json={"competency_evidence": evidence},
    )
    assert skill_gap.status_code == 200, skill_gap.text
    return skill_gap.json()
