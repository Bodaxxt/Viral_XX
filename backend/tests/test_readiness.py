"""
Tests for Readiness Probe and Database Check
"""

from unittest.mock import patch
from fastapi.testclient import TestClient


def test_readiness_healthy(client: TestClient):
    response = client.get("/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["ready"] is True
    assert "dependencies" in data
    assert "database" in data["dependencies"]
    db_dep = data["dependencies"]["database"]
    assert db_dep["connected"] is True
    assert db_dep["status"] == "healthy"
    assert isinstance(db_dep["latency_ms"], (int, float))


def test_readiness_api_prefix(client: TestClient):
    response = client.get("/api/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["ready"] is True


def test_readiness_failure_returns_503(client: TestClient):
    with patch("backend.app.api.v1.endpoints.health.check_db_health") as mock_check:
        mock_check.return_value = {
            "status": "unhealthy",
            "connected": False,
            "latency_ms": 12.5,
            "error": "database disk image is malformed",
        }
        response = client.get("/ready")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "not_ready"
        assert data["ready"] is False
        assert data["dependencies"]["database"]["connected"] is False
        assert "malformed" in data["dependencies"]["database"]["error"]
