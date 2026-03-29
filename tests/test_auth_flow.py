from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def test_health() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


def test_register_login_refresh_logout_flow() -> None:
    email = f"user-{uuid4().hex[:8]}@example.com"
    password = "StrongPass123"

    register_payload = {
        "email": email,
        "full_name": "Test User",
        "password": password,
        "organization_name": "Test Org",
    }

    with TestClient(app) as client:
        register_response = client.post("/api/v1/auth/register", json=register_payload)
        assert register_response.status_code == 201
        register_data = register_response.json()
        assert "access_token" in register_data
        assert "refresh_token" in register_data

        login_response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
        assert login_response.status_code == 200
        login_data = login_response.json()

        me_response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {login_data['access_token']}"},
        )
        assert me_response.status_code == 200
        assert me_response.json()["email"] == email

        refresh_response = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": login_data["refresh_token"]},
        )
        assert refresh_response.status_code == 200
        rotated_tokens = refresh_response.json()
        assert "access_token" in rotated_tokens
        assert "refresh_token" in rotated_tokens

        logout_response = client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": rotated_tokens["refresh_token"]},
        )
        assert logout_response.status_code == 204
