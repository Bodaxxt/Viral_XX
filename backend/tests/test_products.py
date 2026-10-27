"""
Tests for Products and Catalog API (Proof of Concept)
"""

from fastapi.testclient import TestClient


def test_get_catalog_success(client: TestClient):
    response = client.get("/api/v1/tenants/al-noor-jewelry/catalog")
    assert response.status_code == 200
    data = response.json()
    assert data["tenant_id"] == "al-noor-jewelry"
    assert data["currency"] == "QAR"
    assert data["count"] == 2
    assert len(data["products"]) == 2

    first_prod = data["products"][0]
    assert first_prod["tenant_id"] == "al-noor-jewelry"
    assert first_prod["sku"] in ["SKU-EM-101", "SKU-SAP-102"]
    assert first_prod["inventory"] is not None
    assert "stock_count" in first_prod["inventory"]
    assert "available_count" in first_prod["inventory"]


def test_catalog_category_filter(client: TestClient):
    response = client.get("/api/v1/tenants/al-noor-jewelry/catalog?category=Necklaces")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 1
    assert data["products"][0]["id"] == "J-101"
    assert data["products"][0]["category"] == "Necklaces"


def test_catalog_max_budget_filter(client: TestClient):
    response = client.get("/api/v1/tenants/al-noor-jewelry/catalog?max_budget=20000")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 1
    assert data["products"][0]["id"] == "J-102"
    assert data["products"][0]["base_price"] <= 20000


def test_catalog_search_query(client: TestClient):
    response = client.get("/api/v1/tenants/al-noor-jewelry/catalog?q=sapphire")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 1
    assert data["products"][0]["id"] == "J-102"


def test_catalog_in_stock_only(client: TestClient):
    # J-101 has stock=2, reserved=0 -> available=2
    # J-102 has stock=1, reserved=1 -> available=0
    response = client.get("/api/v1/tenants/al-noor-jewelry/catalog?in_stock_only=true")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 1
    assert data["products"][0]["id"] == "J-101"
    assert data["products"][0]["inventory"]["in_stock"] is True


def test_catalog_invalid_budget_validation(client: TestClient):
    response = client.get("/api/v1/tenants/al-noor-jewelry/catalog?max_budget=-50")
    assert response.status_code == 422
    data = response.json()
    assert data["error"]["code"] == "VALIDATION_ERROR"


def test_catalog_non_existent_tenant_returns_404(client: TestClient):
    response = client.get("/api/v1/tenants/fake-tenant/catalog")
    assert response.status_code == 404
    data = response.json()
    assert data["error"]["code"] == "HTTP_404"
