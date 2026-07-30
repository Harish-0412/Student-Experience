from .conftest import headers


def test_admin_can_manage_competency_and_create_template(phase2_env: dict) -> None:
    client = phase2_env["client"]
    admin_headers = headers(phase2_env["ids"]["admin"], "admin")
    competency_response = client.post(
        "/api/v1/admin/competencies",
        headers=admin_headers,
        json={
            "slug": "sql-querying",
            "name": "SQL Querying",
            "description": "Write correct analytical SQL queries.",
            "category": "data",
            "prerequisite_slugs": [],
        },
    )
    assert competency_response.status_code == 201, competency_response.text
    competency = competency_response.json()

    update_response = client.patch(
        f"/api/v1/admin/competencies/{competency['id']}",
        headers=admin_headers,
        json={"description": "Write and optimize analytical SQL queries."},
    )
    assert update_response.status_code == 200, update_response.text
    assert update_response.json()["version"] == 2
    assert "optimize" in update_response.json()["description"]

    template_response = client.post(
        "/api/v1/admin/goal-templates",
        headers=admin_headers,
        json={
            "slug": "sql-assessment",
            "name": "SQL Assessment Preparation",
            "description": "Prepare for a practical SQL assessment.",
            "category": "career",
            "matching_terms": ["sql assessment"],
            "default_duration_weeks": 4,
            "default_target_level": 3,
            "measurable_outcome": "Score at least 80 percent on a timed SQL assessment",
            "success_criteria": ["Pass two timed SQL practice assessments"],
            "requirements": [
                {
                    "competency_slug": "sql-querying",
                    "target_level": 3,
                    "estimated_hours": 24,
                    "required": True,
                    "prerequisite_slugs": [],
                }
            ],
        },
    )
    assert template_response.status_code == 201, template_response.text
    assert template_response.json()["slug"] == "sql-assessment"


def test_student_cannot_use_admin_endpoints(phase2_env: dict) -> None:
    response = phase2_env["client"].post(
        "/api/v1/admin/competencies",
        headers=headers(phase2_env["ids"]["student"], "student"),
        json={
            "slug": "unauthorized-skill",
            "name": "Unauthorized Skill",
            "description": "This record must not be created.",
            "category": "test",
            "prerequisite_slugs": [],
        },
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


def test_admin_template_rejects_prerequisite_cycles(phase2_env: dict) -> None:
    response = phase2_env["client"].post(
        "/api/v1/admin/goal-templates",
        headers=headers(phase2_env["ids"]["admin"], "admin"),
        json={
            "slug": "cyclic-template",
            "name": "Cyclic Template",
            "description": "A deliberately invalid graph.",
            "category": "test",
            "matching_terms": ["cycle"],
            "default_duration_weeks": 4,
            "measurable_outcome": "Demonstrate cycle validation",
            "success_criteria": ["The template is rejected"],
            "requirements": [
                {
                    "competency_slug": "python-fundamentals",
                    "target_level": 2,
                    "estimated_hours": 10,
                    "required": True,
                    "prerequisite_slugs": ["data-analysis-python"],
                },
                {
                    "competency_slug": "data-analysis-python",
                    "target_level": 2,
                    "estimated_hours": 10,
                    "required": True,
                    "prerequisite_slugs": ["python-fundamentals"],
                },
            ],
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "cyclic_template_graph"


def test_admin_competency_update_rejects_ontology_cycle(phase2_env: dict) -> None:
    client = phase2_env["client"]
    admin_headers = headers(phase2_env["ids"]["admin"], "admin")
    with phase2_env["session_factory"]() as db:
        from sqlalchemy import select

        from astrapath.phase2.models import Competency

        python = db.scalar(
            select(Competency).where(Competency.slug == "python-fundamentals")
        )
        assert python is not None
        python_id = python.id

    response = client.patch(
        f"/api/v1/admin/competencies/{python_id}",
        headers=admin_headers,
        json={"prerequisite_slugs": ["data-analysis-python"]},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "cyclic_competency_graph"
