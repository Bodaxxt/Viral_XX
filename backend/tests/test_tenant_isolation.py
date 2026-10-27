"""
Tests for Multi-Tenant Boundary Isolation
Ensures that no tenant's catalog, inventory, or metadata can leak into another tenant's requests.
"""

from fastapi.testclient import TestClient


def test_cross_tenant_catalog_isolation(client: TestClient):
    # Retrieve Al Noor's catalog
    res_alnoor = client.get("/api/v1/tenants/al-noor-jewelry/catalog")
    assert res_alnoor.status_code == 200
    alnoor_data = res_alnoor.json()

    # Retrieve Saffron Table's catalog
    res_saffron = client.get("/api/v1/tenants/saffron-table/catalog")
    assert res_saffron.status_code == 200
    saffron_data = res_saffron.json()

    alnoor_ids = {p["id"] for p in alnoor_data["products"]}
    saffron_ids = {p["id"] for p in saffron_data["products"]}

    # Verify no intersection whatsoever
    assert len(alnoor_ids.intersection(saffron_ids)) == 0

    # Ensure all returned products strictly match their requested tenant_id
    for p in alnoor_data["products"]:
        assert p["tenant_id"] == "al-noor-jewelry"

    for p in saffron_data["products"]:
        assert p["tenant_id"] == "saffron-table"


def test_empty_catalog_for_tenant_without_products(client: TestClient):
    # Vitalis Health has no products seeded in the fixture
    res_vitalis = client.get("/api/v1/tenants/vitalis-health/catalog")
    assert res_vitalis.status_code == 200
    vitalis_data = res_vitalis.json()
    assert vitalis_data["count"] == 0
    assert len(vitalis_data["products"]) == 0
    assert vitalis_data["tenant_id"] == "vitalis-health"


def test_search_cannot_match_across_tenants(client: TestClient):
    # Saffron Table has "Degustation" in name/sku
    # Searching for "Degustation" in Al Noor's catalog MUST return 0 results
    response = client.get("/api/v1/tenants/al-noor-jewelry/catalog?q=Degustation")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 0
    assert len(data["products"]) == 0
