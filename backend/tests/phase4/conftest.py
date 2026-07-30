import uuid
from collections.abc import Iterator
from datetime import date, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from astrapath.enums import GoalStatus, Role, UserStatus
from astrapath.models import Goal, User
from astrapath.phase4.standalone import create_phase4_app


@pytest.fixture
def phase4_env() -> Iterator[dict[str, Any]]:
    app = create_phase4_app()
    session_factory = app.state.session_factory
    with session_factory() as db:
        student = User(
            email=f"student-{uuid.uuid4()}@example.com",
            full_name="Phase Four Student",
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
            full_name="Phase Four Admin",
            role=Role.ADMIN,
            status=UserStatus.ACTIVE,
        )
        db.add_all([student, other_student, admin])
        db.flush()
        goal = Goal(
            student_id=student.id,
            title="Master algorithms",
            raw_statement="Build verified mastery of core algorithms",
            target_date=date.today() + timedelta(days=5),
            status=GoalStatus.ACTIVE,
        )
        other_goal = Goal(
            student_id=other_student.id,
            title="Learn databases",
            raw_statement="Learn database design",
            target_date=date.today() + timedelta(days=30),
            status=GoalStatus.ACTIVE,
        )
        db.add_all([goal, other_goal])
        db.commit()
        ids = {
            "student": student.id,
            "other_student": other_student.id,
            "admin": admin.id,
            "goal": goal.id,
            "other_goal": other_goal.id,
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
