from collections.abc import Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from astrapath.config import Settings
from astrapath.db import Base, get_db
from astrapath.enums import Role, UserStatus
from astrapath.main import create_app
from astrapath.models import User
from astrapath.security import hash_password

TEST_PASSWORD = "Strong-Test-Password-42"


@pytest.fixture
def session_factory() -> Generator[sessionmaker[Session], None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection: Any, _connection_record: Any) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    yield factory
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def app_client(
    session_factory: sessionmaker[Session],
) -> Generator[tuple[TestClient, Any], None, None]:
    settings = Settings(
        environment="test",
        database_url="sqlite://",
        auth_mode="local",
        jwt_secret="test-secret-with-at-least-thirty-two-characters",
        access_token_minutes=15,
        refresh_token_days=30,
    )
    app = create_app(settings)

    def override_db() -> Generator[Session, None, None]:
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as client:
        yield client, app


@pytest.fixture
def client(app_client: tuple[TestClient, Any]) -> TestClient:
    return app_client[0]


def register_student(
    client: TestClient,
    *,
    email: str = "student@example.com",
    name: str = "Test Student",
) -> dict[str, Any]:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": name, "password": TEST_PASSWORD},
    )
    assert response.status_code == 201, response.text
    return response.json()


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_admin(
    app_client: tuple[TestClient, Any],
    session_factory: sessionmaker[Session],
    *,
    email: str = "admin@example.com",
) -> tuple[User, dict[str, str]]:
    _client, app = app_client
    with session_factory() as db:
        admin = User(
            email=email,
            full_name="Test Admin",
            role=Role.ADMIN,
            status=UserStatus.ACTIVE,
            password_hash=hash_password(TEST_PASSWORD),
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)
        admin_id = admin.id
    access_token, _ = app.state.token_service.create_access_token(admin_id, Role.ADMIN, 1)
    with session_factory() as db:
        stored = db.get(User, admin_id)
        assert stored is not None
        db.expunge(stored)
    return stored, bearer(access_token)


@pytest.fixture
def admin_identity(
    app_client: tuple[TestClient, Any],
    session_factory: sessionmaker[Session],
) -> tuple[User, dict[str, str]]:
    return create_admin(app_client, session_factory)


@pytest.fixture
def student_identity(client: TestClient) -> tuple[dict[str, Any], dict[str, str]]:
    token_pair = register_student(client)
    return token_pair["user"], bearer(token_pair["access_token"])


def onboard(client: TestClient, headers: dict[str, str]) -> dict[str, Any]:
    response = client.post(
        "/api/v1/student/onboarding",
        headers=headers,
        json={
            "display_name": "Test Student",
            "timezone": "Asia/Kolkata",
            "locale": "en-IN",
            "education_level": "Undergraduate",
            "institution": "Example University",
            "weekly_learning_minutes": 420,
            "learning_preferences": ["project-based", "visual"],
            "availability": {"monday": [{"start": "18:00", "end": "19:00"}]},
            "device_access": ["laptop"],
            "accessibility_needs": [],
            "consent_scopes": [],
            "onboarding_completed": True,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def create_goal(
    client: TestClient,
    headers: dict[str, str],
    *,
    description: str | None = "Build and demonstrate a complete portfolio project.",
    success_criteria: list[str] | None = None,
) -> dict[str, Any]:
    response = client.post(
        "/api/v1/student/goals",
        headers=headers,
        json={
            "title": "Build a Python portfolio project",
            "raw_statement": "Build and publish a tested Python portfolio project",
            "description": description,
            "category": "software-development",
            "target_date": "2099-12-31",
            "priority": 4,
            "success_criteria": success_criteria
            if success_criteria is not None
            else ["Repository is public", "Automated tests pass"],
            "assumptions": ["Laptop access remains available"],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()

