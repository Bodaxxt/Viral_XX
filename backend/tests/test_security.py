"""
Tests for Security Guardrails and Middleware Protections
"""

import pytest
from fastapi.testclient import TestClient


def test_directory_traversal_path_blocked(client: TestClient):
    # Attempting to traverse upward using encoded dots returns 403 Forbidden
    response = client.get("/api/v1/tenants/%2e%2e/%2e%2e/package.json")
    assert response.status_code == 403
    data = response.json()
    assert "Path traversal attempt detected" in data["detail"]


def test_sensitive_env_file_blocked(client: TestClient):
    response = client.get("/.env")
    assert response.status_code == 404
    data = response.json()
    assert "Access to sensitive file denied" in data["detail"]


def test_sensitive_database_file_blocked(client: TestClient):
    response = client.get("/viral_x.db")
    assert response.status_code == 404
    data = response.json()
    assert "Access to sensitive file denied" in data["detail"]


def test_sensitive_package_json_blocked(client: TestClient):
    response = client.get("/package.json")
    assert response.status_code == 404
    data = response.json()
    assert "Access to sensitive file denied" in data["detail"]


def test_request_size_limit_exceeded(client: TestClient):
    # Payload exceeding 1 MB (1,048,576 bytes)
    large_payload = {"data": "X" * (1_048_576 + 500)}
    response = client.post("/api/v1/tenants", json=large_payload)
    assert response.status_code == 413
    data = response.json()
    assert "exceeds maximum allowed limit" in data["detail"]


def test_cors_headers_present(client: TestClient):
    response = client.options(
        "/api/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"
