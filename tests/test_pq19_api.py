from fastapi.testclient import TestClient
from src.api import app, METRICS

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_metric_catalog_contains_five_metrics():
    response = client.get("/metrics")
    assert response.status_code == 200
    assert response.json()["count"] == 5
    ids = {item["metric_id"] for item in response.json()["metrics"]}
    assert ids == set(METRICS)


def test_monthly_metric_requires_month():
    response = client.get("/metrics/M01")
    assert response.status_code == 422


def test_m22_requires_sprint_id():
    response = client.get("/metrics/M22")
    assert response.status_code == 422


def test_unknown_metric_returns_404():
    response = client.get("/metrics/M99?month=2026-09")
    assert response.status_code == 404


def test_m01_returns_governance_metadata():
    response = client.get("/metrics/M01?month=2026-09")
    assert response.status_code == 200
    body = response.json()
    assert body["metric_id"] == "M01"
    assert body["source_table"] == "fact_headcount_monthly / dim_employee"
    assert body["owner_team"] == "HR Analytics"
    assert body["data_freshness"]["latest_source_date"] is not None


def test_m13_returns_ratio_unit():
    response = client.get("/metrics/M13?month=2026-09")
    assert response.status_code == 200
    assert response.json()["unit"] == "ratio"
    assert response.json()["value"] is not None


def test_m22_requires_existing_sprint():
    response = client.get("/metrics/M22?sprint_id=NOT_A_REAL_SPRINT")
    assert response.status_code == 404
