from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from astrapath.models import AgentRun, WorkflowState
from tests.conftest import create_goal, onboard


def test_goal_clarification_runs_agents_1_2_and_20(
    client: TestClient,
    student_identity: tuple[dict, dict[str, str]],
    session_factory: sessionmaker[Session],
) -> None:
    _student, headers = student_identity
    onboard(client, headers)
    goal = create_goal(client, headers)

    response = client.post(
        f"/api/v1/student/goals/{goal['id']}/clarify",
        headers={**headers, "X-Correlation-ID": "test-workflow-001"},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["clarification_questions"] == []
    assert data["workflow"]["status"] == "completed"
    assert data["workflow"]["current_step"] == "phase_2_feasibility"

    with session_factory() as db:
        runs = list(db.scalars(select(AgentRun).order_by(AgentRun.started_at)))
        workflows = db.scalar(select(func.count(WorkflowState.id)))
    assert workflows == 1
    assert [run.agent_name for run in runs] == [
        "StudentProfileAgent",
        "GoalClarificationAgent",
        "SupervisorGovernanceAgent",
    ]
    assert all(run.input_hash and run.output_hash for run in runs)


def test_clarification_pauses_for_missing_student_input(
    client: TestClient,
    student_identity: tuple[dict, dict[str, str]],
) -> None:
    _student, headers = student_identity
    onboard(client, headers)
    goal = create_goal(client, headers, success_criteria=[])
    response = client.post(
        f"/api/v1/student/goals/{goal['id']}/clarify",
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["workflow"]["status"] == "input_required"
    assert response.json()["clarification_questions"]
