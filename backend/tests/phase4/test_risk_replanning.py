from datetime import UTC, datetime

from tests.phase4.conftest import headers


def test_execution_context_risk_and_approval_based_replan(phase4_env: dict) -> None:
    client = phase4_env["client"]
    ids = phase4_env["ids"]
    admin_headers = headers(ids["admin"], "admin")
    student_headers = headers(ids["student"], "student")
    source_time = datetime.now(UTC).isoformat()

    synced = client.put(
        f"/api/v1/admin/phase4/goals/{ids['goal']}/execution-context",
        headers=admin_headers,
        json={
            "plan_ref": "phase3-plan-opaque",
            "plan_version": 7,
            "planned_task_count": 10,
            "completed_task_count": 1,
            "planned_milestone_count": 4,
            "completed_milestone_count": 0,
            "planned_weekly_minutes": 900,
            "weekly_capacity_minutes": 300,
            "schedule_adherence": 0.25,
            "source_updated_at": source_time,
        },
    )
    assert synced.status_code == 200
    assert synced.json()["plan_ref"] == "phase3-plan-opaque"

    stale = client.put(
        f"/api/v1/admin/phase4/goals/{ids['goal']}/execution-context",
        headers=admin_headers,
        json={
            "plan_ref": "phase3-plan-opaque",
            "plan_version": 7,
            "planned_task_count": 10,
            "completed_task_count": 1,
            "planned_milestone_count": 4,
            "completed_milestone_count": 0,
            "planned_weekly_minutes": 900,
            "weekly_capacity_minutes": 300,
            "schedule_adherence": 0.25,
            "source_updated_at": source_time,
        },
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "stale_execution_context"

    progress = client.post(
        f"/api/v1/student/goals/{ids['goal']}/progress/rebuild",
        headers=student_headers,
    )
    assert progress.status_code == 200

    scan = client.post(
        f"/api/v1/student/goals/{ids['goal']}/risks/scan",
        headers=student_headers,
        json={"open_blockers": ["Technical environment access is blocked"]},
    )
    assert scan.status_code == 200
    risks = scan.json()["risks"]
    risk = next(item for item in risks if item["requires_admin_review"])

    proposal = client.post(
        f"/api/v1/student/goals/{ids['goal']}/replans",
        headers=student_headers,
        json={
            "risk_id": risk["id"],
            "base_plan_ref": "phase3-plan-opaque",
            "base_plan_version": 7,
            "preserve_completed_work": True,
            "student_constraints": {"max_weekly_minutes": 300},
        },
    )
    assert proposal.status_code == 201
    body = proposal.json()
    assert body["status"] == "proposed"
    assert body["admin_review_required"] is True
    assert body["preserves_completed_work"] is True

    premature = client.post(
        f"/api/v1/student/replans/{body['id']}/decision",
        headers=student_headers,
        json={
            "decision": "approve",
            "expected_version": body["version"],
            "reason": "The reduced scope works for me.",
        },
    )
    assert premature.status_code == 409

    admin_approved = client.post(
        f"/api/v1/admin/phase4/replans/{body['id']}/decision",
        headers=admin_headers,
        json={
            "decision": "approve",
            "expected_version": body["version"],
            "reason": "The proposal preserves completed work.",
        },
    )
    assert admin_approved.status_code == 200
    assert admin_approved.json()["status"] == "proposed"
    assert admin_approved.json()["admin_review_required"] is False

    approved = client.post(
        f"/api/v1/student/replans/{body['id']}/decision",
        headers=student_headers,
        json={
            "decision": "approve",
            "expected_version": admin_approved.json()["version"],
            "reason": "Apply this after Phase 3 validates the patch.",
        },
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved_pending_phase3"

    agents = client.get(
        "/api/v1/admin/phase4/agents",
        headers=admin_headers,
    )
    assert agents.status_code == 200
    assert len(agents.json()) == 10

    runs = client.get(
        "/api/v1/admin/phase4/agent-runs",
        headers=admin_headers,
    )
    assert runs.status_code == 200
    assert {item["agent_name"] for item in runs.json()} >= {
        "ProgressTrackingAgent",
        "RiskBlockerDetectionAgent",
        "AdaptiveReplanningAgent",
    }
