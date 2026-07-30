import uuid
from collections.abc import Iterator
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from astrapath.enums import GoalStatus, Role, UserStatus
from astrapath.models import Goal, StudentProfile, User
from astrapath.phase2.repository import Phase2Repository
from astrapath.phase2.standalone import create_phase2_app


@pytest.fixture
def phase2_env() -> Iterator[dict]:
    app = create_phase2_app()
    session_factory = app.state.session_factory
    with session_factory() as db:
        student = User(
            email=f"student-{uuid.uuid4()}@example.com",
            full_name="Phase Two Student",
            role=Role.STUDENT,
            status=UserStatus.ACTIVE,
        )
        other_student = User(
            email=f"other-{uuid.uuid4()}@example.com",
            full_name="Other Student",
            role=Role.STUDENT,
            status=UserStatus.ACTIVE,
        )
        admin = User(
            email=f"admin-{uuid.uuid4()}@example.com",
            full_name="Phase Two Admin",
            role=Role.ADMIN,
            status=UserStatus.ACTIVE,
        )
        db.add_all([student, other_student, admin])
        db.flush()
        db.add(
            StudentProfile(
                user_id=student.id,
                display_name="Phase Two Student",
                weekly_learning_minutes=600,
                onboarding_completed=True,
            )
        )
        goals = {
            "ml": Goal(
                student_id=student.id,
                title="ML internship",
                raw_statement="I want to get a machine learning internship",
                target_date=date.today() + timedelta(weeks=12),
                status=GoalStatus.DRAFT,
            ),
            "dsa": Goal(
                student_id=student.id,
                title="Coding interview",
                raw_statement="Prepare for a data structures coding interview",
                target_date=date.today() + timedelta(weeks=6),
                status=GoalStatus.DRAFT,
            ),
            "calculus": Goal(
                student_id=student.id,
                title="Calculus exam",
                raw_statement="I need to pass my calculus exam",
                target_date=date.today() + timedelta(weeks=6),
                status=GoalStatus.DRAFT,
            ),
        }
        db.add_all(goals.values())
        Phase2Repository(db).seed_catalog()
        db.commit()
        ids = {
            "student": student.id,
            "other_student": other_student.id,
            "admin": admin.id,
            **{name: goal.id for name, goal in goals.items()},
        }

    client = TestClient(app)
    yield {
        "app": app,
        "client": client,
        "session_factory": session_factory,
        "ids": ids,
    }
    client.close()
    app.state.engine.dispose()


def headers(actor_id: uuid.UUID, role: str) -> dict[str, str]:
    return {
        "X-AstraPath-Actor-Id": str(actor_id),
        "X-AstraPath-Actor-Role": role,
    }
