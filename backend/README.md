# Viral-X Python + FastAPI Backend Foundation (Sprint 2.5)

This directory contains the Python-first backend foundation for the Viral-X platform, established during **Sprint 2.5**.

It runs alongside the existing Node.js/Express service, providing modern AI orchestration capabilities, typed API validation via Pydantic, parameterized database access via SQLAlchemy, and a verified read-only catalog vertical slice proof-of-concept.

---

## Architecture & Technology Stack

- **Framework:** [FastAPI](https://fastapi.tiangolo.com/) (Asynchronous, high-performance web API)
- **Validation:** [Pydantic v2](https://docs.pydantic.dev/) (Strict type schemas and settings)
- **Database Access:** [SQLAlchemy 2.0](https://www.sqlalchemy.org/) (Transactional, parameterized, SQLite PRAGMA enforcement)
- **Server:** [Uvicorn](https://www.uvicorn.org/) (ASGI production server)
- **Testing:** [Pytest](https://docs.pytest.org/) with `httpx` and disposable in-memory SQLite fixtures

---

## Directory Structure

```text
backend/
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── endpoints/
│   │       │   ├── health.py        ← /health, /ready, /api/health probes
│   │       │   ├── tenants.py       ← GET /api/v1/tenants, /api/v1/tenants/{id}
│   │       │   └── products.py      ← GET /api/v1/tenants/{id}/catalog (Proof of Concept)
│   │       └── api.py               ← API v1 router aggregator
│   ├── core/
│   │   ├── config.py                ← Pydantic BaseSettings, secret masking
│   │   ├── logging.py               ← Structured logging with PCI/PII scrubber
│   │   └── middleware.py            ← Traversal guardrails, 1MB body limit, 30s timeout
│   ├── db/
│   │   ├── models.py                ← Exact SQLAlchemy models matching schema.sql
│   │   └── session.py               ← Engine, WAL mode, foreign key enforcement, health check
│   ├── repositories/
│   │   ├── base.py                  ← Generic repository
│   │   ├── tenant_repository.py     ← Tenant workspace queries
│   │   └── product_repository.py    ← Parameterized catalog queries with tenant isolation
│   ├── schemas/
│   │   ├── health.py                ← Health & readiness Pydantic response models
│   │   ├── tenant.py                ← Tenant workspace Pydantic models
│   │   └── product.py               ← Product, inventory & catalog Pydantic models
│   ├── services/
│   │   └── catalog_service.py       ← Business logic, inventory calculation, attribute parsing
│   └── main.py                      ← FastAPI factory, CORS, exception handlers, router mounts
├── tests/
│   ├── conftest.py                  ← In-memory SQLite fixture and TestClient override
│   ├── test_config.py               ← Config loading and secret masking tests
│   ├── test_health.py               ← Liveness probe tests
│   ├── test_readiness.py            ← Readiness probe and DB failure mock tests
│   ├── test_products.py             ← Proof-of-concept catalog and filter tests
│   ├── test_tenants.py              ← Tenant listing and filtering tests
│   ├── test_tenant_isolation.py     ← Strict cross-tenant boundary isolation tests
│   └── test_security.py             ← Path traversal, sensitive file block, and payload size limit tests
├── .env.example                     ← Environment configuration template
├── requirements.txt                 ← Pinned dependency ranges
└── README.md                        ← This documentation
```

---

## Getting Started

### 1. Prerequisites
- Python 3.10+ (tested with Python 3.13)
- Existing SQLite database (`viral_x.db` at project root)

### 2. Environment Setup
```bash
# Create and activate a virtual environment (optional if using global Python)
python -m venv .venv
source .venv/bin/activate  # On Linux/macOS
.venv\Scripts\activate     # On Windows

# Install dependencies
pip install -r backend/requirements.txt
```

### 3. Configuration
Copy the `.env.example` file to `.env` if not already present:
```bash
cp backend/.env.example .env
```
Key configuration parameters:
- `DATABASE_URL`: Defaults to `sqlite:///./viral_x.db` (auto-resolves to project root).
- `CORS_ORIGINS`: Comma-separated allowed origins (e.g., `http://localhost:3000,http://127.0.0.1:3000`).
- `MAX_REQUEST_SIZE_BYTES`: Enforced request body limit (default: 1,048,576 bytes / 1 MB).
- `REQUEST_TIMEOUT_SECONDS`: Request processing timeout (default: 30 seconds).

### 4. Running the Development Server
```bash
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```
Interactive API documentation will be available at:
- Swagger UI: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- ReDoc: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

---

## Running the Automated Test Suite

The test suite runs against a disposable, in-memory SQLite database (`sqlite:///:memory:`) and never mutates persistent production or demo databases:

```bash
python -m pytest backend/tests -v
```

All 29 tests pass with zero failures:
- Startup, liveness, and readiness probes
- Database connectivity & failure degradation (503 response)
- Tenant retrieval and category filtering
- Catalog search, price filtering, and stock grounding
- Cross-tenant catalog isolation guarantees
- Path traversal & sensitive file blocking (403/404)
- 1MB payload size limit enforcement (413)
- Secret masking in logs and configuration representations

---

## Implemented API Endpoints (Sprint 2.5)

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| `GET` | `/health` | Liveness check (FastAPI process status) | Public |
| `GET` | `/ready` | Readiness check (validates database connection) | Public |
| `GET` | `/api/health` | Alternate liveness check prefix | Public |
| `GET` | `/api/ready` | Alternate readiness check prefix | Public |
| `GET` | `/api/v1/tenants` | List all active tenant businesses | Public |
| `GET` | `/api/v1/tenants/{tenant_id}` | Get metadata for a specific tenant | Public |
| `GET` | `/api/v1/tenants/{tenant_id}/catalog` | **Proof of Concept:** Retrieve typed product catalog with inventory | Public (Demo) / Tenant API Key (Future Live) |

---

## Security Defenses

1. **Path Traversal Defense:** `SecurityAndTraversalMiddleware` intercepts and rejects any URI with `..`, `%2e%2e`, backslashes (`\`, `%5c`), or null bytes (`%00`) with `403 Forbidden`.
2. **Sensitive File Blocking:** Direct access to `.env`, `.git`, `.db`, `package.json`, or source code is blocked with `404 Not Found`.
3. **Payload Protection:** `RequestSizeLimitMiddleware` terminates requests with bodies exceeding 1 MB with `413 Payload Too Large`.
4. **Secret Masking:** Sensitive AI keys (`GEMINI_API_KEY`, etc.) are excluded from `repr()` and log output. Card numbers are scrubbed via regex filters.
5. **Database Parameterization:** All queries use SQLAlchemy ORM or bound parameters, eliminating SQL injection vectors.
6. **Multi-Tenant Scoping:** All catalog queries require explicit `tenant_id` filtering in both the product table and the inventory join.
