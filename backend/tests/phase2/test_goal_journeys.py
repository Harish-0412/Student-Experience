from datetime import date, timedelta

from astrapath.phase2.contracts import StudentCompetencyInput
from astrapath.phase2.repository import Phase2Repository

from .conftest import headers


def seed_student_skills(env: dict, skills: list[dict]) -> None:
    with env["session_factory"]() as db:
        Phase2Repository(db).upsert_student_competencies(
            env["ids"]["student"],
            [StudentCompetencyInput(**skill) for skill in skills],
        )
        db.commit()


def test_student_can_list_active_goal_templates(phase2_env: dict) -> None:
    response = phase2_env["client"].get(
        "/api/v1/goal-templates",
        headers=headers(phase2_env["ids"]["student"], "student"),
    )

    assert response.status_code == 200
    templates = response.json()
    assert {template["slug"] for template in templates} == {
        "calculus-exam",
        "data-structures-interview",
        "machine-learning-internship",
    }
    assert all(template["active"] for template in templates)


def run_until_skill_gap(
    env: dict,
    goal_key: str,
    *,
    clarify_payload: dict,
    feasibility_payload: dict,
    evidence: list[dict],
) -> tuple[dict, dict, dict]:
    client = env["client"]
    actor_headers = headers(env["ids"]["student"], "student")
    goal_id = env["ids"][goal_key]
    clarification = client.post(
        f"/api/v1/goals/{goal_id}/clarify",
        headers=actor_headers,
        json=clarify_payload,
    )
    assert clarification.status_code == 200, clarification.text
    feasibility = client.post(
        f"/api/v1/goals/{goal_id}/feasibility",
        headers=actor_headers,
        json=feasibility_payload,
    )
    assert feasibility.status_code == 200, feasibility.text
    skill_gap = client.post(
        f"/api/v1/goals/{goal_id}/skill-gap",
        headers=actor_headers,
        json={"competency_evidence": evidence},
    )
    assert skill_gap.status_code == 200, skill_gap.text
    return clarification.json(), feasibility.json(), skill_gap.json()


def test_machine_learning_goal_is_measurable_and_prerequisite_aware(
    phase2_env: dict,
) -> None:
    seed_student_skills(
        phase2_env,
        [
            {
                "competency_slug": "python-fundamentals",
                "proficiency_level": 3,
                "confidence": 0.9,
                "source": "project",
                "evidence_refs": ["github-project-001"],
            },
            {
                "competency_slug": "algebra-functions",
                "proficiency_level": 2,
                "confidence": 0.8,
                "source": "course",
                "evidence_refs": ["course-algebra"],
            },
            {
                "competency_slug": "data-analysis-python",
                "proficiency_level": 2,
                "confidence": 0.75,
                "source": "project",
                "evidence_refs": ["notebook-001"],
            },
        ],
    )
    clarification, feasibility, workflow = run_until_skill_gap(
        phase2_env,
        "ml",
        clarify_payload={
            "raw_goal": "I want to learn ML and get a machine learning internship",
            "weekly_hours": 10,
            "target_date": (date.today() + timedelta(weeks=12)).isoformat(),
        },
        feasibility_payload={"weekly_hours": 10},
        evidence=[
            {
                "competency_slug": "statistics",
                "proficiency_level": 1,
                "confidence": 0.55,
                "source": "self_reported",
            }
        ],
    )

    assert clarification["clarified_goal"]["template_slug"] == "machine-learning-internship"
    assert len(clarification["clarified_goal"]["success_criteria"]) >= 3
    assert any(
        "proficiency level 3" in criterion
        for criterion in clarification["clarified_goal"]["success_criteria"]
    )
    assert any(
        (date.today() + timedelta(weeks=12)).isoformat() in criterion
        for criterion in clarification["clarified_goal"]["success_criteria"]
    )
    assert "portfolio projects" in clarification["clarified_goal"]["measurable_outcome"]
    assert feasibility["category"] == "challenging_but_possible"
    assert feasibility["estimated_effort_hours"]["minimum"] > 0
    assert feasibility["scenario_options"]

    skill_gap = workflow["skill_gap"]
    graph = workflow["graph"]
    assert "machine-learning-fundamentals" in skill_gap["gap_priority"]
    assert graph["nodes"]
    assert graph["edges"]
    assert graph["nodes"][-1]["node_type"] == "outcome"
    assert any(
        card["decision"] == (
            "Study Statistics before Machine Learning Fundamentals"
        )
        and card["approval_required"]
        for card in graph["decision_cards"]
    )

    nodes_by_title = {node["title"]: node for node in graph["nodes"]}
    relevant_edge = next(
        edge
        for edge in graph["edges"]
        if edge["source_node_id"] == nodes_by_title["Statistics"]["id"]
        and edge["target_node_id"]
        == nodes_by_title["Machine Learning Fundamentals"]["id"]
    )
    assert relevant_edge["relationship_type"] == "prerequisite"
    assert (
        nodes_by_title["Statistics"]["sequence_order"]
        < nodes_by_title["Machine Learning Fundamentals"]["sequence_order"]
    )


def test_limited_availability_makes_dsa_goal_unlikely(phase2_env: dict) -> None:
    clarification, feasibility, workflow = run_until_skill_gap(
        phase2_env,
        "dsa",
        clarify_payload={"weekly_hours": 4},
        feasibility_payload={
            "weekly_hours": 4,
            "existing_commitment_hours_per_week": 1,
        },
        evidence=[
            {
                "competency_slug": "programming-problem-solving",
                "proficiency_level": 2,
                "confidence": 0.8,
                "source": "course",
            }
        ],
    )

    assert clarification["clarified_goal"]["template_slug"] == "data-structures-interview"
    assert feasibility["category"] == "unlikely_under_current_conditions"
    assert any("Extend the target" in item for item in feasibility["recommended_adjustments"])
    assert feasibility["decision_cards"][0]["approval_required"] is True
    assert "graphs-dynamic-programming" in workflow["graph"]["optional_branches"]


def test_calculus_goal_uses_existing_algebra_evidence(phase2_env: dict) -> None:
    seed_student_skills(
        phase2_env,
        [
            {
                "competency_slug": "algebra-functions",
                "proficiency_level": 3,
                "confidence": 0.95,
                "source": "mentor",
                "evidence_refs": ["mentor-check-01"],
            },
            {
                "competency_slug": "limits-continuity",
                "proficiency_level": 2,
                "confidence": 0.85,
                "source": "diagnostic",
                "evidence_refs": ["limits-quiz-01"],
            },
        ],
    )
    _, feasibility, workflow = run_until_skill_gap(
        phase2_env,
        "calculus",
        clarify_payload={"weekly_hours": 13},
        feasibility_payload={"weekly_hours": 13},
        evidence=[],
    )

    assert feasibility["category"] == "feasible_with_constraints"
    by_slug = {
        item["slug"]: item
        for item in workflow["skill_gap"]["required_competencies"]
    }
    assert by_slug["algebra-functions"]["classification"] == "verified"
    assert by_slug["limits-continuity"]["classification"] == "developing"
    assert workflow["graph"]["core_path"][0] == "limits-continuity"


def test_graph_and_competency_reads_require_completed_flow(phase2_env: dict) -> None:
    client = phase2_env["client"]
    actor_headers = headers(phase2_env["ids"]["student"], "student")
    goal_id = phase2_env["ids"]["ml"]

    graph = client.get(f"/api/v1/goals/{goal_id}/graph", headers=actor_headers)
    competencies = client.get(
        f"/api/v1/goals/{goal_id}/competencies", headers=actor_headers
    )

    assert graph.status_code == 409
    assert competencies.status_code == 409
    assert graph.json()["error"]["code"] == "goal_intelligence_step_required"


def test_feasibility_cannot_hide_required_competencies(phase2_env: dict) -> None:
    client = phase2_env["client"]
    actor_headers = headers(phase2_env["ids"]["student"], "student")
    goal_id = phase2_env["ids"]["ml"]
    clarification = client.post(
        f"/api/v1/goals/{goal_id}/clarify",
        headers=actor_headers,
        json={"weekly_hours": 10},
    )
    assert clarification.status_code == 200

    response = client.post(
        f"/api/v1/goals/{goal_id}/feasibility",
        headers=actor_headers,
        json={"excluded_competencies": ["statistics"]},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == (
        "required_competencies_cannot_be_excluded"
    )


def test_student_cannot_access_another_students_goal(phase2_env: dict) -> None:
    response = phase2_env["client"].post(
        f"/api/v1/goals/{phase2_env['ids']['ml']}/clarify",
        headers=headers(phase2_env["ids"]["other_student"], "student"),
        json={},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"
