"""Authentication, session handling, and account protection."""

import pytest

from tests.conftest import VALID_PASSWORD, register_and_login


def test_register_creates_user_and_default_workspace(client):
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "new@example.com", "password": VALID_PASSWORD, "full_name": "New User"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert body["data"]["email"] == "new@example.com"
    # A user with no workspace has a broken app on first load.
    assert body["data"]["last_workspace_id"]


def test_register_never_returns_password_material(client):
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "leak@example.com", "password": VALID_PASSWORD},
    )
    assert "password" not in response.text.lower() or "hashed_password" not in response.text


@pytest.mark.parametrize(
    "password",
    [
        "a",  # too short -- accepted by the previous implementation
        "short1A",
        "alllowercase123",
        "ALLUPPERCASE123",
        "NoDigitsHereAtAll",
        "password123",  # common
    ],
)
def test_weak_passwords_are_rejected(client, password):
    response = client.post(
        "/api/v1/auth/register", json={"email": "weak@example.com", "password": password}
    )
    assert response.status_code == 422, f"{password!r} was accepted"
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_duplicate_email_is_rejected(client, alice):
    response = client.post(
        "/api/v1/auth/register", json={"email": alice.email, "password": VALID_PASSWORD}
    )
    assert response.status_code == 409


def test_login_sets_httponly_refresh_cookie(client, alice):
    response = client.post(
        "/api/v1/auth/login", json={"email": alice.email, "password": VALID_PASSWORD}
    )
    assert response.status_code == 200
    assert response.json()["data"]["access_token"]

    cookie_header = response.headers.get("set-cookie", "")
    assert "refresh_token=" in cookie_header
    # The refresh token must not be reachable from JavaScript.
    assert "httponly" in cookie_header.lower()


def test_login_with_wrong_password_fails(client, alice):
    response = client.post(
        "/api/v1/auth/login", json={"email": alice.email, "password": "Wrong-Password-1"}
    )
    assert response.status_code == 401


def test_login_error_does_not_reveal_whether_account_exists(client, alice):
    known = client.post(
        "/api/v1/auth/login", json={"email": alice.email, "password": "Wrong-Password-1"}
    )
    unknown = client.post(
        "/api/v1/auth/login", json={"email": "ghost@example.com", "password": "Wrong-Password-1"}
    )
    assert known.status_code == unknown.status_code == 401
    assert known.json()["error"]["message"] == unknown.json()["error"]["message"]


def test_account_locks_after_repeated_failures(client, alice):
    from app.services.auth_service import MAX_FAILED_ATTEMPTS

    for _ in range(MAX_FAILED_ATTEMPTS):
        client.post(
            "/api/v1/auth/login", json={"email": alice.email, "password": "Wrong-Password-1"}
        )

    # Even the correct password is refused while locked.
    response = client.post(
        "/api/v1/auth/login", json={"email": alice.email, "password": VALID_PASSWORD}
    )
    assert response.status_code == 429
    assert "try again" in response.json()["error"]["message"].lower()


def test_refresh_rotates_the_token(client, alice):
    login = client.post(
        "/api/v1/auth/login", json={"email": alice.email, "password": VALID_PASSWORD}
    )
    original_cookie = client.cookies.get("refresh_token")

    refreshed = client.post("/api/v1/auth/refresh")
    assert refreshed.status_code == 200
    assert refreshed.json()["data"]["access_token"]
    assert client.cookies.get("refresh_token") != original_cookie


def test_reusing_a_rotated_refresh_token_kills_the_session_family(client, alice):
    client.post("/api/v1/auth/login", json={"email": alice.email, "password": VALID_PASSWORD})
    stolen = client.cookies.get("refresh_token")

    assert client.post("/api/v1/auth/refresh").status_code == 200

    # Replaying the old token looks like theft: every session must be revoked.
    client.cookies.set("refresh_token", stolen)
    assert client.post("/api/v1/auth/refresh").status_code == 401

    # And the token issued by the legitimate rotation is dead too.
    assert client.post("/api/v1/auth/refresh").status_code == 401


def test_logout_revokes_the_refresh_token(client, alice):
    client.post("/api/v1/auth/login", json={"email": alice.email, "password": VALID_PASSWORD})
    assert client.post("/api/v1/auth/logout").status_code == 200
    assert client.post("/api/v1/auth/refresh").status_code == 401


def test_me_requires_a_token(client):
    assert client.get("/api/v1/auth/me").status_code == 401


def test_me_rejects_a_forged_token(client):
    response = client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer not.a.real.token"}
    )
    assert response.status_code == 401


def test_refresh_token_is_not_accepted_as_an_access_token(client, alice):
    client.post("/api/v1/auth/login", json={"email": alice.email, "password": VALID_PASSWORD})
    refresh = client.cookies.get("refresh_token")
    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {refresh}"})
    assert response.status_code == 401


def test_password_change_requires_current_password(client, alice):
    response = client.post(
        "/api/v1/users/me/password",
        json={"current_password": "Wrong-Password-1", "new_password": "Another-Valid-9"},
        headers=alice.headers(),
    )
    assert response.status_code == 400


def test_password_change_signs_out_other_sessions(client, alice):
    client.post("/api/v1/auth/login", json={"email": alice.email, "password": VALID_PASSWORD})

    response = client.post(
        "/api/v1/users/me/password",
        json={"current_password": VALID_PASSWORD, "new_password": "Another-Valid-9"},
        headers=alice.headers(),
    )
    assert response.status_code == 200
    assert client.post("/api/v1/auth/refresh").status_code == 401


def test_user_cannot_escalate_their_own_role(client, alice):
    """`UserUpdate` has no `role` field, so the attempt is silently ignored."""
    response = client.patch(
        "/api/v1/users/me",
        json={"full_name": "Renamed", "role": "ADMIN", "is_verified": True},
        headers=alice.headers(),
    )
    assert response.status_code == 200
    assert response.json()["data"]["full_name"] == "Renamed"
    assert response.json()["data"]["role"] != "ADMIN"
    assert response.json()["data"]["is_verified"] is False
