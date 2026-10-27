"""
Tests for Tenants API
"""

from fastapi.testclient import TestClient


def test_list_all_tenants(client: TestClient):
    response = client.get("/api/v1/tenants")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 3
    tenant_ids = [t["id"] for t in data["tenants"]]
    assert "al-noor-jewelry" in tenant_ids
    assert "saffron-table" in tenant_ids
    assert "vitalis-health" in tenant_ids


def test_filter_tenants_by_category(client: TestClient):
    response = client.get("/api/v1/tenants?category=jewelry")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 1
    assert data["tenants"][0]["id"] == "al-noor-jewelry"
    assert data["tenants"][0]["category"] == "jewelry"


def test_get_single_tenant_success(client: TestClient):
    response = client.get("/api/v1/tenants/al-noor-jewelry")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "al-noor-jewelry"
    assert data["currency"] == "QAR"
    assert "+974" in data["whatsapp_number"]
    assert "GIA" in data["policy_summary"]


def test_get_single_tenant_not_found(client: TestClient):
    response = client.get("/api/v1/tenants/non-existent-tenant")
    assert response.status_code == 404
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "HTTP_404"
