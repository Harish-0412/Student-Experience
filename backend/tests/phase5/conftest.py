from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.conftest import bearer, register_student


@pytest.fixture
def planning_student(client: TestClient) -> dict[str, Any]:
    token_pair = register_student(
        client,
        email="phase5-planner@example.com",
        name="Phase Five Planning Student",
    )
    headers = bearer(token_pair["access_token"])
    onboarding = client.post(
        "/api/v1/student/onboarding",
        headers=headers,
        json={
            "display_name": "Phase Five Planning Student",
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
    return {"headers": headers, "user": token_pair["user"]}
