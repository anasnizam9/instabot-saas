from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)

test_email = f"user-{uuid4().hex[:8]}@example.com"
test_password = "StrongPass123"


def test_org_lifecycle() -> None:
    with TestClient(app) as client:
        register_payload = {
            "email": test_email,
            "full_name": "Test User",
            "password": test_password,
            "organization_name": "Test Org",
        }

        register_response = client.post("/api/v1/auth/register", json=register_payload)
        assert register_response.status_code == 201
        register_data = register_response.json()
        access_token = register_data["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        list_response = client.get("/api/v1/organizations", headers=headers)
        assert list_response.status_code == 200
        orgs = list_response.json()
        assert len(orgs) == 1
        org_id = orgs[0]["id"]

        detail_response = client.get(f"/api/v1/organizations/{org_id}", headers=headers)
        assert detail_response.status_code == 200
        org_detail = detail_response.json()
        assert org_detail["name"] == "Test Org"
        assert len(org_detail["members"]) >= 1

        my_role_response = client.get(f"/api/v1/organizations/{org_id}/my-role", headers=headers)
        assert my_role_response.status_code == 200
        assert my_role_response.json()["role"] == "owner"

        new_org_payload = {"name": "Second Org"}
        create_response = client.post("/api/v1/organizations", json=new_org_payload, headers=headers)
        assert create_response.status_code == 201
        new_org = create_response.json()
        assert new_org["name"] == "Second Org"

        list_response2 = client.get("/api/v1/organizations", headers=headers)
        assert list_response2.status_code == 200
        assert len(list_response2.json()) == 2
