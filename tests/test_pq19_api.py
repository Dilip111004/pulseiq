import json
import time
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.testclient import TestClient

from src.api import app, METRICS
from src.auth import hash_password, create_access_token
import src.auth as auth_module

client = TestClient(app)
TEST_PASSWORD = "Temporary-Test-Password-2026!"

TEST_USERS = {
    f"{role.lower()}.test": {
        "password_hash": hash_password(TEST_PASSWORD),
        "role": role,
    }
    for role in ("ADMIN", "EXECUTIVE", "HR", "MANAGER")
}


@pytest.fixture(autouse=True)
def configure_test_auth(monkeypatch):
    monkeypatch.setenv(
        "PULSEIQ_TOKEN_SECRET",
        "temporary-test-secret-at-least-32-characters"
    )
    monkeypatch.setenv("PULSEIQ_AUTH_USERS", json.dumps(TEST_USERS))


@pytest.fixture
def auth_headers():
    def make_headers(role="ADMIN"):
        username = f"{role.lower()}.test"
        token = create_access_token({"username": username, "role": role})
        return {"Authorization": f"Bearer {token}"}
    return make_headers


def test_health_endpoint_is_public():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_metrics_requires_authentication():
    response = client.get("/metrics")
    assert response.status_code == 401


def test_metric_catalog_contains_five_metrics_for_admin(auth_headers):
    response = client.get("/metrics", headers=auth_headers("ADMIN"))
    assert response.status_code == 200
    assert response.json()["count"] == 5
    ids = {item["metric_id"] for item in response.json()["metrics"]}
    assert ids == set(METRICS)


def test_executive_catalog_excludes_m22(auth_headers):
    response = client.get("/metrics", headers=auth_headers("EXECUTIVE"))
    assert response.status_code == 200
    ids = {item["metric_id"] for item in response.json()["metrics"]}
    assert ids == {"M01", "M07", "M09", "M13"}


@pytest.mark.parametrize("role", ["HR", "MANAGER"])
def test_restricted_roles_cannot_list_metrics(auth_headers, role):
    response = client.get("/metrics", headers=auth_headers(role))
    assert response.status_code == 403


def test_monthly_metric_requires_month(auth_headers):
    response = client.get("/metrics/M01", headers=auth_headers())
    assert response.status_code == 422


def test_m22_requires_sprint_id(auth_headers):
    response = client.get("/metrics/M22", headers=auth_headers())
    assert response.status_code == 422


def test_unknown_metric_returns_404(auth_headers):
    response = client.get(
        "/metrics/M99?month=2026-09",
        headers=auth_headers()
    )
    assert response.status_code == 404


def test_m01_returns_governance_metadata(auth_headers):
    response = client.get(
        "/metrics/M01?month=2026-09",
        headers=auth_headers()
    )
    assert response.status_code == 200
    body = response.json()
    assert body["metric_id"] == "M01"
    assert body["source_table"] == "fact_headcount_monthly / dim_employee"
    assert body["owner_team"] == "HR Analytics"
    assert body["data_freshness"]["latest_source_date"] is not None


def test_m13_returns_ratio_unit(auth_headers):
    response = client.get(
        "/metrics/M13?month=2026-09",
        headers=auth_headers()
    )
    assert response.status_code == 200
    assert response.json()["unit"] == "ratio"
    assert response.json()["value"] is not None


def test_m22_requires_existing_sprint(auth_headers):
    response = client.get(
        "/metrics/M22?sprint_id=NOT_A_REAL_SPRINT",
        headers=auth_headers()
    )
    assert response.status_code == 404


def test_executive_cannot_access_m22(auth_headers):
    response = client.get(
        "/metrics/M22?sprint_id=SP-01",
        headers=auth_headers("EXECUTIVE")
    )
    assert response.status_code == 403


def test_login_returns_access_token():
    response = client.post(
        "/auth/login",
        json={"username": "admin.test", "password": TEST_PASSWORD}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 1800
    assert body["role"] == "ADMIN"
    assert body["access_token"]


def test_login_rejects_wrong_password():
    response = client.post(
        "/auth/login",
        json={"username": "admin.test", "password": "incorrect"}
    )
    assert response.status_code == 401


def test_tampered_token_is_rejected():
    token = create_access_token({
        "username": "admin.test",
        "role": "ADMIN"
    })
    response = client.get(
        "/metrics",
        headers={"Authorization": f"Bearer {token}tampered"}
    )
    assert response.status_code == 401


def test_m22_threshold_text_is_parsed():
    from src.api import parse_minimum_group_size
    assert parse_minimum_group_size({"minimum_group_size": "5 tasks"}) == 5


def test_missing_threshold_fails_closed():
    from src.api import parse_minimum_group_size

    with pytest.raises(HTTPException) as exc:
        parse_minimum_group_size({"minimum_group_size": None})
    assert exc.value.status_code == 503


def test_invalid_threshold_fails_closed():
    from src.api import parse_minimum_group_size

    with pytest.raises(HTTPException) as exc:
        parse_minimum_group_size({"minimum_group_size": "unknown"})
    assert exc.value.status_code == 503


def test_small_population_is_suppressed(monkeypatch, auth_headers):
    import src.api as api_module

    monkeypatch.setattr(
        api_module, "dictionary_row",
        lambda metric_id: {"minimum_group_size": "5"}
    )
    monkeypatch.setattr(
        api_module, "calculate_metric",
        lambda metric_id, month, sprint_id: (100.0, 4, "2026-09-30", month)
    )

    response = client.get(
        "/metrics/M01?month=2026-09",
        headers=auth_headers()
    )
    assert response.status_code == 403

def test_expired_token_is_rejected(auth_headers, monkeypatch):
    monkeypatch.setattr(auth_module, "TOKEN_MAX_AGE_SECONDS", 0)

    headers = auth_headers("ADMIN")
    time.sleep(1)

    response = client.get("/metrics", headers=headers)

    assert response.status_code == 401
    assert "expired" in response.json()["detail"].lower()
