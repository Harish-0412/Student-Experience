from tests.phase4.conftest import headers

TRUSTED_HASH = "a" * 64
UNTRUSTED_HASH = "b" * 64


def test_trusted_evidence_updates_mastery(phase4_env: dict) -> None:
    client = phase4_env["client"]
    ids = phase4_env["ids"]
    admin_headers = headers(ids["admin"], "admin")
    student_headers = headers(ids["student"], "student")

    receipt = client.post(
        "/api/v1/admin/phase4/storage-receipts",
        headers=admin_headers,
        json={
            "storage_key": "evidence/trusted.txt",
            "media_type": "text/plain",
            "size_bytes": 128,
            "sha256": TRUSTED_HASH,
            "scanner_status": "clean",
        },
    )
    assert receipt.status_code == 201

    report = client.post(
        "/api/v1/student/evidence",
        headers=student_headers,
        json={
            "goal_id": str(ids["goal"]),
            "competency_ref": "binary-search",
            "task_ref": "opaque-task",
            "original_name": "solution.txt",
            "media_type": "text/plain",
            "size_bytes": 128,
            "sha256": TRUSTED_HASH,
            "storage_key": "evidence/trusted.txt",
            "content_text": (
                "Binary search halves the sorted search space after every comparison."
            ),
            "acceptance_criteria": [
                "Binary search halves the sorted search space",
            ],
            "idempotency_key": "trusted-evidence-0001",
        },
    )
    assert report.status_code == 201
    assert report.json()["decision"] == "verified"
    assert report.json()["quality_score"] == 1

    mastery = client.get(
        f"/api/v1/student/goals/{ids['goal']}/mastery",
        headers=student_headers,
    )
    assert mastery.status_code == 200
    assert mastery.json()[0]["evidence_count"] == 1


def test_untrusted_evidence_requires_admin_decision(phase4_env: dict) -> None:
    client = phase4_env["client"]
    ids = phase4_env["ids"]
    admin_headers = headers(ids["admin"], "admin")
    student_headers = headers(ids["student"], "student")

    report = client.post(
        "/api/v1/student/evidence",
        headers=student_headers,
        json={
            "goal_id": str(ids["goal"]),
            "competency_ref": "binary-search",
            "original_name": "untrusted.txt",
            "media_type": "text/plain",
            "size_bytes": 96,
            "sha256": UNTRUSTED_HASH,
            "storage_key": "evidence/unregistered.txt",
            "content_text": "Binary search halves a sorted search space.",
            "acceptance_criteria": ["halves sorted search space"],
            "idempotency_key": "untrusted-evidence-01",
        },
    )
    assert report.status_code == 201
    assert report.json()["decision"] == "admin_review_required"
    assert "unverified_storage_object" in report.json()["integrity_flags"]

    student_evidence = client.get(
        "/api/v1/student/evidence",
        headers=student_headers,
        params={"goal_id": str(ids["goal"])},
    )
    assert student_evidence.status_code == 200
    assert [item["id"] for item in student_evidence.json()] == [
        report.json()["evidence_id"]
    ]

    queued = client.get(
        "/api/v1/admin/phase4/evidence/review-queue",
        headers=admin_headers,
    )
    assert queued.status_code == 200
    assert len(queued.json()) == 1

    decision = client.post(
        f"/api/v1/admin/phase4/evidence/{report.json()['evidence_id']}/decision",
        headers=admin_headers,
        json={
            "decision": "verified",
            "reason": "Artifact was manually checked in the trusted review environment.",
        },
    )
    assert decision.status_code == 200
    assert decision.json()["status"] == "verified"
