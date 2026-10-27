"""
Tests for Health Liveness Endpoint
"""

from fastapi.testclient import TestClient


def test_liveness_root(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "service" in data
    assert "version" in data
    assert "environment" in data
    assert "timestamp" in data


def test_liveness_api_prefix(client: TestClient):
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "Viral-X" in data["service"]


def test_liveness_v1_prefix(client: TestClient):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
