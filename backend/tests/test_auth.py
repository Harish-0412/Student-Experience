from fastapi.testclient import TestClient

from tests.conftest import TEST_PASSWORD, bearer, register_student


def test_registration_is_student_only_and_me_works(client: TestClient) -> None:
    rejected = client.post(
        "/api/v1/auth/register",
        json={
            "email": "attacker@example.com",
            "full_name": "Role Selector",
            "password": TEST_PASSWORD,
            "role": "admin",
        },
    )
    assert rejected.status_code == 422

    token_pair = register_student(client)
    assert token_pair["user"]["role"] == "student"
    me = client.get(
        "/api/v1/auth/me",
        headers=bearer(token_pair["access_token"]),
    )
    assert me.status_code == 200
    assert me.json()["email"] == "student@example.com"


def test_login_refresh_rotation_and_logout(client: TestClient) -> None:
    registered = register_student(client)
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "STUDENT@example.com", "password": TEST_PASSWORD},
    )
    assert login.status_code == 200
    assert login.json()["access_token"] != registered["access_token"]

    old_refresh = login.json()["refresh_token"]
    rotated = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": old_refresh},
    )
    assert rotated.status_code == 200
    new_refresh = rotated.json()["refresh_token"]
    assert new_refresh != old_refresh

    replay = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": old_refresh},
    )
    assert replay.status_code == 401
    assert replay.json()["error"]["code"] == "invalid_refresh_token"

    logout = client.post(
        "/api/v1/auth/logout",
        headers=bearer(rotated.json()["access_token"]),
        json={"refresh_token": new_refresh},
    )
    assert logout.status_code == 200
    after_logout = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": new_refresh},
    )
    assert after_logout.status_code == 401


def test_password_strength_and_duplicate_email(client: TestClient) -> None:
    weak = client.post(
        "/api/v1/auth/register",
        json={
            "email": "weak@example.com",
            "full_name": "Weak Password",
            "password": "onlylowercase",
        },
    )
    assert weak.status_code == 422

    register_student(client)
    duplicate = client.post(
        "/api/v1/auth/register",
        json={
            "email": "STUDENT@EXAMPLE.COM",
            "full_name": "Duplicate",
            "password": TEST_PASSWORD,
        },
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "email_exists"

