from tests.phase4.conftest import headers


def test_focus_assessment_mastery_and_progress_loop(phase4_env: dict) -> None:
    client = phase4_env["client"]
    ids = phase4_env["ids"]
    student_headers = headers(ids["student"], "student")
    admin_headers = headers(ids["admin"], "admin")

    started = client.post(
        "/api/v1/student/focus-sessions",
        headers=student_headers,
        json={
            "goal_id": str(ids["goal"]),
            "task_ref": "task-opaque-1",
            "milestone_ref": "milestone-opaque-1",
            "objective": "Practice binary search boundary cases",
            "planned_minutes": 30,
            "idempotency_key": "focus-session-0001",
        },
    )
    assert started.status_code == 201
    repeated = client.post(
        "/api/v1/student/focus-sessions",
        headers=student_headers,
        json={
            "goal_id": str(ids["goal"]),
            "task_ref": "task-opaque-1",
            "milestone_ref": "milestone-opaque-1",
            "objective": "Practice binary search boundary cases",
            "planned_minutes": 30,
            "idempotency_key": "focus-session-0001",
        },
    )
    assert repeated.status_code == 201
    assert repeated.json()["id"] == started.json()["id"]

    completed = client.post(
        f"/api/v1/student/focus-sessions/{started.json()['id']}/complete",
        headers=student_headers,
        json={
            "expected_version": 1,
            "actual_minutes": 28,
            "distraction_count": 1,
            "blocker_notes": [],
            "reflection": "Boundary checks now make sense.",
            "accomplished": True,
        },
    )
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"

    assessment = client.post(
        "/api/v1/admin/phase4/assessments",
        headers=admin_headers,
        json={
            "goal_id": str(ids["goal"]),
            "competency_ref": "binary-search",
            "title": "Binary Search Check",
            "assessment_type": "quiz",
            "instructions": "Answer each question.",
            "questions": [
                {
                    "id": "q1",
                    "prompt": "What precondition does binary search require?",
                    "kind": "multiple_choice",
                    "options": ["Sorted input", "Linked input"],
                    "correct_answer": "Sorted input",
                    "points": 2,
                }
            ],
            "passing_percentage": 70,
        },
    )
    assert assessment.status_code == 201
    published = client.patch(
        f"/api/v1/admin/phase4/assessments/{assessment.json()['id']}/status",
        headers=admin_headers,
        json={"status": "published", "expected_version": 1},
    )
    assert published.status_code == 200

    attempt = client.post(
        f"/api/v1/student/assessments/{assessment.json()['id']}/attempts",
        headers=student_headers,
        json={
            "answers": [{"question_id": "q1", "answer": "Sorted input"}],
            "idempotency_key": "assessment-attempt-0001",
        },
    )
    assert attempt.status_code == 201
    assert attempt.json()["percentage"] == 100
    assert attempt.json()["passed"] is True

    mastery = client.get(
        f"/api/v1/student/goals/{ids['goal']}/mastery",
        headers=student_headers,
    )
    assert mastery.status_code == 200
    assert mastery.json()[0]["competency_ref"] == "binary-search"
    assert mastery.json()[0]["evidence_count"] == 1

    progress = client.get(
        f"/api/v1/student/goals/{ids['goal']}/progress",
        headers=student_headers,
    )
    assert progress.status_code == 200
    assert progress.json()["focus_minutes"] == 28
    assert progress.json()["assessment_count"] == 1
    assert progress.json()["mastery_progress"] > 0
