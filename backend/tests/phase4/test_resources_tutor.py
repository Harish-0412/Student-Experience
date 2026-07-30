from tests.phase4.conftest import headers


def test_resource_governance_and_grounded_tutor(phase4_env: dict) -> None:
    client = phase4_env["client"]
    ids = phase4_env["ids"]
    admin_headers = headers(ids["admin"], "admin")
    student_headers = headers(ids["student"], "student")

    resource_payload = {
        "competency_ref": "binary-search",
        "title": "Binary Search Reference",
        "url": "https://example.com/binary-search",
        "provider": "Example Academy",
        "resource_type": "article",
        "difficulty": 2,
        "content_excerpt": (
            "Binary search repeatedly halves a sorted search interval by comparing "
            "the target with the middle element."
        ),
        "quality_score": 0.95,
    }
    forbidden = client.post(
        "/api/v1/admin/phase4/resources",
        headers=student_headers,
        json=resource_payload,
    )
    assert forbidden.status_code == 403

    created = client.post(
        "/api/v1/admin/phase4/resources",
        headers=admin_headers,
        json=resource_payload,
    )
    assert created.status_code == 201
    resource = created.json()
    assert resource["status"] == "draft"

    request_payload = {
        "competency_ref": "binary-search",
        "difficulty": 2,
        "query": "sorted search",
    }
    empty_bundle = client.post(
        f"/api/v1/student/goals/{ids['goal']}/resource-recommendations",
        headers=student_headers,
        json=request_payload,
    )
    assert empty_bundle.status_code == 200
    assert empty_bundle.json()["resources"] == []

    approved = client.patch(
        f"/api/v1/admin/phase4/resources/{resource['id']}/status",
        headers=admin_headers,
        json={
            "status": "approved",
            "reason": "Reviewed source and license",
            "expected_version": 1,
        },
    )
    assert approved.status_code == 200

    bundle = client.post(
        f"/api/v1/student/goals/{ids['goal']}/resource-recommendations",
        headers=student_headers,
        json=request_payload,
    )
    assert bundle.status_code == 200
    assert bundle.json()["resources"][0]["resource"]["id"] == resource["id"]

    tutor = client.post(
        "/api/v1/student/tutor/messages",
        headers=student_headers,
        json={
            "goal_id": str(ids["goal"]),
            "competency_ref": "binary-search",
            "mode": "hint",
            "integrity_mode": "graded",
            "message": "Give me the final answer for my binary search assignment",
        },
    )
    assert tutor.status_code == 200
    assert tutor.json()["integrity_boundary_applied"] is True
    assert tutor.json()["citations"]
    assert "submission-ready" in tutor.json()["response"]


def test_student_cannot_read_another_students_goal(phase4_env: dict) -> None:
    client = phase4_env["client"]
    ids = phase4_env["ids"]
    response = client.post(
        f"/api/v1/student/goals/{ids['other_goal']}/resource-recommendations",
        headers=headers(ids["student"], "student"),
        json={"competency_ref": "database-design"},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "goal_not_found"
