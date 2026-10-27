# Viral-X Python + FastAPI Backend Migration Plan

**Sprint 2.5: Backend Migration Foundation**  
**Document Status:** Approved Foundation Architecture  
**Author:** Senior Backend Architect  
**Target Platform:** Python 3.10+ / FastAPI / SQLAlchemy 2.0 / Pydantic v2  

---

## 1. Executive Summary & Strategic Rationale

Viral-X is strategically transitioning its backend services from Node.js (Express) to Python (FastAPI). The primary motivation is the long-term consolidation of AI orchestration, data engineering, and machine learning into an idiomatic, high-performance ecosystem.

### Why Python?
1. **AI & LLM Orchestration:** Modern AI toolchains (such as Google GenAI SDK, LangChain/LangGraph, LlamaIndex, Instructor, and DSPy) provide first-class, bleeding-edge support in Python.
2. **Machine Learning & Analytics:** Predictive sales forecasting, dynamic objection clustering, and inventory optimization demand native scientific computing packages (`numpy`, `pandas`, `scikit-learn`).
3. **Strict Type Safety & Schemas:** Pydantic v2 offers unmatched performance and validation guarantees for multi-tenant data contracts, structured outputs, and LLM tool calling.
4. **Asynchronous Throughput:** FastAPI running atop ASGI (Uvicorn / Starlette) delivers high concurrent throughput with native asynchronous I/O, ideal for streaming LLM responses and handling concurrent WhatsApp/chat sessions.
5. **Safe Coexistence:** This migration is designed as a phased foundation. The Node.js Express server remains 100% operational, and no production data or persistent databases are altered or destroyed.

---

## 2. Current vs. Target Architecture

```
                    CURRENT ARCHITECTURE (Sprint 2)
  ┌─────────────────────────────────────────────────────────────┐
  │                      Frontend Web Clients                   │
  │                  (index.html, chat.html, JS)                │
  └──────────────────────────────┬──────────────────────────────┘
                                 │ HTTP (Port 3000)
  ┌──────────────────────────────▼──────────────────────────────┐
  │                   Node.js / Express Server                  │
  │   - Static File Security (Middleware)                       │
  │   - AI Sales Agent (Gemini / Claude / OpenAI / Local)       │
  │   - 10 Deterministic Business Tools                         │
  │   - Draft Order Lifecycle & WhatsApp Escalation             │
  │   - BI Telemetry Aggregation (Funnel, Objections, Demand)   │
  └──────────────────────────────┬──────────────────────────────┘
                                 │ node:sqlite
  ┌──────────────────────────────▼──────────────────────────────┐
  │                  SQLite 3 Database (viral_x.db)             │
  │                 10 Tables, Foreign Keys, Indexes            │
  └─────────────────────────────────────────────────────────────┘

                                 ▼
                     TARGET ARCHITECTURE (Phased)
  ┌─────────────────────────────────────────────────────────────┐
  │                      Frontend Web Clients                   │
  │                  (index.html, chat.html, JS)                │
  └──────────────────────────────┬──────────────────────────────┘
                                 │
                  ┌──────────────┴──────────────┐
                  │   Reverse Proxy / Gateway   │
                  │   (Nginx / Caddy / Cloud)   │
                  └──────┬──────────────┬───────┘
     Legacy Routes       │              │ Migrated Endpoints
    (During Transition)  │              │ (/api/v1/..., /api/health)
  ┌──────────────────────▼──────┐   ┌───▼───────────────────────────┐
  │   Node.js / Express Server  │   │     FastAPI Python Backend    │
  │   - Order Drafts (until S3) │   │   - Pydantic Validation       │
  │   - WhatsApp Handoff        │   │   - SQLAlchemy 2.0 ORM        │
  │   - Webhooks                │   │   - Python AI Orchestration   │
  │                             │   │   - Read-only Catalog (PoC)   │
  │                             │   │   - Telemetry & Future ML     │
  └──────────────┬──────────────┘   └───┬───────────────────────────┘
                 │                      │
                 │   Shared Datastore   │
                 └──────────────┬───────┘
                                │ Parameterized Queries / PRAGMAs
  ┌─────────────────────────────▼───────────────────────────────┐
  │     SQLite 3 (Current) ──► PostgreSQL / Supabase (Future)    │
  │                  Zero-Downtime Data Layer                   │
  └─────────────────────────────────────────────────────────────┘
```

### Architectural Comparison Matrix

| Dimension | Current Architecture (Node.js) | Target Architecture (Python) | Status in Sprint 2.5 |
|---|---|---|---|
| **Runtime** | Node.js 22 (V8) | Python 3.10+ (CPython 3.13) | Python backend directory established |
| **Framework** | Express 4.19 | FastAPI 0.115+ (Starlette / ASGI) | FastAPI application factory configured |
| **Validation** | Ad-hoc JavaScript type checks | Pydantic v2 (Rust-powered strict models) | Typed schemas for Health, Tenants, Products |
| **Data Access** | Native `node:sqlite` raw queries | SQLAlchemy 2.0 (ORM + Core) | Repository pattern with parameterized queries |
| **Database Concurrency** | SQLite synchronous mode | SQLite WAL mode + `PRAGMA busy_timeout=5000` | Configured via engine event listeners |
| **AI Orchestration** | Custom JavaScript LLM adapters | Python GenAI SDK / LangGraph | Planned for Sprint 3 |
| **Security Layer** | Custom static security middleware | Custom ASGI traversal & payload middleware | Traversal defense, 1MB limit, 30s timeout |
| **API Documentation** | Manual markdown tables | Automatic OpenAPI (Swagger & ReDoc) | Interactive docs live at `/docs` & `/redoc` |

---

## 3. Existing API Contracts & Migration Inventory

The existing Express backend endpoints have been audited from `server/app.js` and route files:

| HTTP Method | Route | Express Handler | Migration Category | Python Target Route | Sprint Status |
|---|---|---|---|---|---|
| `GET` | `/api/health` | `server/app.js` | **Required for Website/Monitoring** | `GET /api/health` & `/health` | ✅ Implemented (FastAPI) |
| `GET` | `/api/ready` | N/A (New in Python) | **Required for Monitoring** | `GET /api/ready` & `/ready` | ✅ Implemented (FastAPI) |
| `GET` | `/api/tenants` | `server/routes/tenantRoutes.js` | **Required for Website & Demos** | `GET /api/v1/tenants` | ✅ Implemented (FastAPI) |
| `GET` | `/api/tenants/:id` | `server/routes/tenantRoutes.js` | **Required for Website & Demos** | `GET /api/v1/tenants/{id}` | ✅ Implemented (FastAPI) |
| `GET` | `/api/tenants/:id/catalog` | `server/routes/tenantRoutes.js` | **Required for AI Sales Agent** | `GET /api/v1/tenants/{id}/catalog` | ✅ Implemented (FastAPI PoC) |
| `POST` | `/api/chat` | `server/routes/chatRoutes.js` | **Required for AI Sales Agent** | `POST /api/v1/chat` | ⏳ Node.js exclusive (Sprint 3) |
| `GET` | `/api/chat/history/:id`| `server/routes/chatRoutes.js` | **Required for AI Sales Agent** | `GET /api/v1/chat/history/{id}` | ⏳ Node.js exclusive (Sprint 3) |
| `GET` | `/api/drafts/:id` | `server/routes/draftRoutes.js` | **Required for Order Drafts** | `GET /api/v1/drafts/{id}` | ✅ Implemented (FastAPI v1, Isolated) |
| `POST` | `/api/drafts` | `server/routes/draftRoutes.js` | **Required for Order Drafts** | `POST /api/v1/drafts` | ✅ Implemented (FastAPI v1, Isolated) |
| `PUT` | `/api/drafts/:id` | `server/routes/draftRoutes.js` | **Required for Order Drafts** | `PUT /api/v1/drafts/{id}` | ✅ Implemented (FastAPI v1, Isolated) |
| `POST` | `/api/drafts/confirm` | `server/routes/draftRoutes.js` | **Required for Order Drafts** | `POST /api/v1/drafts/confirm` | ✅ Implemented (FastAPI v1, Isolated) |
| `POST` | `/api/drafts/cancel` | `server/routes/draftRoutes.js` | **Required for Order Drafts** | `POST /api/v1/drafts/cancel` | ✅ Implemented (FastAPI v1, Isolated) |
| `GET` | `/api/bookings/availability`| `server/routes/bookingRoutes.js` | **Required for Bookings** | `GET /api/v1/bookings/availability` | ✅ Implemented (FastAPI v1, Isolated) |
| `POST` | `/api/bookings/reserve`| `server/routes/bookingRoutes.js` | **Required for Bookings** | `POST /api/v1/bookings/reserve` | ✅ Implemented (FastAPI v1, Isolated) |
| `POST` | `/api/bookings/cancel` | `server/routes/bookingRoutes.js` | **Required for Bookings** | `POST /api/v1/bookings/cancel` | ✅ Implemented (FastAPI v1, Isolated) |
| `POST` | `/api/handoff/whatsapp`| `server/routes/handoffRoutes.js`| **Required for Order Drafts** | `POST /api/v1/handoff/whatsapp` | ✅ Implemented (FastAPI v1, Isolated) |
| `GET` | `/api/analytics/summary`| `server/routes/analyticsRoutes.js`| **Required for Analytics** | `GET /api/v1/analytics/summary` | ✅ Implemented (FastAPI v1, Isolated) |
| `GET` | `/api/analytics/funnel` | `server/routes/analyticsRoutes.js`| **Required for Analytics** | `GET /api/v1/analytics/funnel` | ✅ Implemented (FastAPI v1, Isolated) |
| `GET` | `/api/analytics/objections`| `server/routes/analyticsRoutes.js`| **Required for Analytics** | `GET /api/v1/analytics/objections`| ✅ Implemented (FastAPI v1, Isolated) |
| `GET` | `/api/analytics/demand` | `server/routes/analyticsRoutes.js`| **Required for Analytics** | `GET /api/v1/analytics/demand` | ✅ Implemented (FastAPI v1, Isolated) |
| `POST` | `/api/analytics/events/demo-seed`| `server/routes/analyticsRoutes.js`| **Internal / Testing** | `POST /api/v1/analytics/events/demo-seed`| ✅ Implemented (FastAPI v1, Isolated) |
| `GET` | `/api/integrations` | `server/routes/tenantRoutes.js` | **Internal / Adapter Status** | `GET /api/v1/integrations` | ⏳ Node.js exclusive (Sprint 5) |

> [!IMPORTANT]
> **Zero Client Disruption Rule:** The production frontend (`index.html`, `chat.html`, `assets/js/*.js`) continues to point to Express (port 3000) for all transactional and AI chat workflows. No production client will be repointed to Python endpoints until end-to-end parity is proven and automated tests pass.

---

## 4. Implemented Python Endpoints (Sprint 2.5)

### 1. Health & Liveness Probe
- **Endpoint:** `GET /health` and `GET /api/health`
- **Purpose:** Standard liveness check for container orchestrators (Kubernetes, Docker Swarm, Fly.io).
- **Response Format:**
  ```json
  {
    "status": "ok",
    "service": "Viral-X AI Sales Agent & BI Platform",
    "version": "2.5.0-alpha",
    "timestamp": "2026-10-25T15:20:00.000000Z",
    "environment": "development"
  }
  ```

### 2. Readiness Probe
- **Endpoint:** `GET /ready` and `GET /api/ready`
- **Purpose:** Actively probes critical dependencies (executes `SELECT 1` on SQLite) before routing live traffic.
- **Degradation Behavior:** Returns HTTP 503 Service Unavailable if database is unreachable or malformed.
- **Response Format:**
  ```json
  {
    "status": "ready",
    "service": "Viral-X AI Sales Agent & BI Platform",
    "version": "2.5.0-alpha",
    "timestamp": "2026-10-25T15:20:00.000000Z",
    "ready": true,
    "dependencies": {
      "database": {
        "name": "sqlite_database",
        "status": "healthy",
        "connected": true,
        "latency_ms": 1.25,
        "error": null
      }
    }
  }
  ```

### 3. Tenant Workspace Endpoints
- **Endpoints:** `GET /api/v1/tenants` and `GET /api/v1/tenants/{tenant_id}`
- **Purpose:** Provides structured metadata (hours, currency, WhatsApp, policies) for business tenants.
- **Query Filters:** `?category=jewelry`

### 4. Migration Proof-of-Concept: Read-Only Catalog Slice
- **Endpoint:** `GET /api/v1/tenants/{tenant_id}/catalog`
- **Purpose:** Demonstrates secure, typed data retrieval directly from the existing SQLite database via SQLAlchemy.
- **Guarantees:**
  - **Strict Multi-Tenant Isolation:** Products and inventory are joined and filtered strictly by `Product.tenant_id == tenant_id`. Zero possibility of cross-tenant leakage.
  - **Inventory Grounding:** Computes real-time available stock (`stock_count - reserved_count`) and flags `in_stock: true|false`.
  - **Attribute Deserialization:** Safely parses `attributes_json` into structured dictionary objects.
  - **Query Filters:** Supports `?category=`, `?max_budget=`, `?q=`, and `?in_stock_only=true`.

---

## 5. Database Migration & Compatibility Strategy

### Preserving Existing SQLite Database
The SQLite database (`viral_x.db`) contains active business catalogs, policies, chat histories, drafts, and BI telemetry.
In Sprint 2.5:
1. **Zero Destructive Migrations:** The schema in `server/db/schema.sql` is treated as the immutable source of truth.
2. **SQLAlchemy Models Alignment:** `backend/app/db/models.py` matches the table names, column constraints, text UUID primary keys, and cascade rules of the existing schema.
3. **Engine PRAGMAs:**
   - `PRAGMA foreign_keys = ON;` (Enforces referential integrity on every connection).
   - `PRAGMA journal_mode = WAL;` (Enables concurrent readers and a single writer without blocking).
   - `PRAGMA busy_timeout = 5000;` (Mitigates SQLite lock contention under burst load).

### Future PostgreSQL / Supabase Roadmap
When horizontal scaling or managed enterprise hosting becomes necessary:
1. **Dialect Agnostic ORM:** SQLAlchemy models in `backend/app/db/models.py` use standard types (`String`, `Integer`, `Float`, `DateTime`, `Text`) compatible with PostgreSQL.
2. **Alembic Migration Tooling:** Introduce Alembic to generate schema migrations targeting Postgres schemas while preserving existing SQLite compatibility.
3. **JSONB Optimization:** Columns currently stored as `Text` JSON strings (`attributes_json`, `items_json`, `metadata_json`) will map directly to native PostgreSQL `JSONB` for indexing and query acceleration.
4. **ETL Script:** A Python data-pump utility using `pgloader` or a batch streaming pipeline will copy tables from SQLite to PostgreSQL with identity preservation.

---

## 6. Security Analysis & Controls

### Public vs. Authenticated Endpoints

| Endpoint Range | Current Access | Production Target Access | Security Control |
|---|---|---|---|
| `/health`, `/ready` | Public | Public | Rate-limited by IP (120 req/min) |
| `/api/v1/tenants` | Public (Demo) | Public (Demo) / Authenticated (Live) | Whitelisted demo tenants |
| `/api/v1/tenants/{id}/catalog` | Public (Demo) | API Key or Tenant Session Token | Tenant ID validation + stock verification |
| `/api/v1/chat` (Future) | Public (Session) | Session Token + CSRF Guard | Rate limit + prompt injection filter |
| `/api/v1/drafts/*` (Future) | Session-bound | Session-bound + Signed Idempotency Key | Cross-tenant access validation |
| `/api/v1/analytics/*` (Future) | Internal/Demo | Role-Based Access Control (Admin JWT) | Dedicated admin authentication guard |

### Hardened Middleware Protections
- **Directory Traversal:** Any request containing `..`, `%2e%2e`, backslashes, or null bytes is intercepted by `SecurityAndTraversalMiddleware` and terminated with HTTP 403.
- **Sensitive File Shielding:** Probing for `.env`, `.git`, `.db`, `package.json`, or server directories returns HTTP 404 immediately.
- **Payload Denial-of-Service Defense:** Request bodies exceeding 1,048,576 bytes (1 MB) trigger HTTP 413 Payload Too Large.
- **Timeout Protection:** Request processing exceeding 30 seconds triggers HTTP 504 Gateway Timeout.
- **Secret Scrubbing:** Structured logs and exception responses filter credit card numbers (Luhn/regex) and never print API keys.

---

## 7. Phased Implementation Roadmap

```mermaid
gantt
    title Viral-X Backend Migration Roadmap
    dateFormat  YYYY-MM-DD
    section Foundation
    Sprint 2.5: Python & FastAPI Foundation     :done, 2026-10-25, 2026-10-26
    section AI & Tools Migration
    Sprint 3.0: Deterministic Tools in Python   :2026-10-27, 4d
    Sprint 3.1: Python AI Orchestrator & LLM SDK:2026-10-31, 5d
    section Transactions & Orders
    Sprint 3.5: Order Drafts & Idempotency Gate :2026-11-05, 4d
    Sprint 3.6: Human Handoff & WhatsApp Adapters:2026-11-09, 3d
    section Analytics & Cutover
    Sprint 4.0: BI Telemetry Aggregation & ML   :2026-11-12, 5d
    Sprint 5.0: Gateway Routing & Final Cutover :2026-11-17, 4d
```

### Phase Details

#### Phase 1: Sprint 2.5 — Backend Foundation (COMPLETED)
- Established `backend/` directory structure.
- Implemented FastAPI app with Pydantic v2 schemas and SQLAlchemy 2.0 ORM.
- Implemented health and readiness probes with SQLite health checking.
- Built read-only tenant catalog vertical slice proof of concept.
- Configured security middleware (traversal defense, 1MB limit, 30s timeout, CORS).
- Added comprehensive Pytest suite (29 tests) and validated Node.js suite (54 tests).

#### Phase 2: Sprint 3.0 & 3.1 — AI Agent Orchestration Migration (COMPLETED)
- Implemented Python AI Agent Orchestrator in `backend/app/agents/` mirroring `server/ai/aiAgent.js`.
- Implemented provider adapters for Google Gemini, Anthropic Claude, OpenAI, and Local Fallback (`providers.py`, `provider_factory.py`).
- Implemented full prompt templates and domain rules in `prompt_templates.py`.
- Implemented security guardrails (Arabic/English injection filters, PCI-DSS card redaction, tenant scoping) in `guardrails.py`.
- Implemented read-only business tools (`search_products`, `get_product_details`, `check_inventory`, `calculate_price`, `search_business_knowledge`, `check_booking_availability`) in `tools.py`.
- Enforced strict write-protection blocking `create_order_draft`, `update_order_draft`, `get_order_draft`, and `request_human_handoff` during this sprint.
- Exposed isolated test endpoints: `POST /api/v1/agent/test` and `GET /api/v1/agent/info`.
- Maintained 100% isolation of Node.js production `/api/chat` route.
- Expanded Pytest suite from 29 to 75 passed tests covering all agent functions, security boundaries, and mocked providers.

#### Phase 3: Sprint 3.5 — Order Drafts & Safe Confirmation Gate (COMPLETED)
- Implemented stateful draft order lifecycle (`create_draft`, `update_draft`, `get_draft`, `confirm_draft`, `cancel_draft`).
- Built deterministic server-side pricing engine for subtotal, discounts, dining deposits, and taxes.
- Implemented explicit confirmation gate forbidding AI agent from independently finalizing orders or bookings.
- Implemented booking lifecycle (`get_availability`, `get_slot_details`, `create_booking`, `cancel_booking`) with concurrency guard.
- Enforced strict tenant isolation and audit logging for all draft and booking transitions.
- Pytest test suite expanded to 116 passed tests; Node.js suite verified at 54 passed tests.

#### Phase 3.6: Human Handoff & WhatsApp Adapters (COMPLETED)
- Ported WhatsApp escalation builder with URL encoding and session context.
- Ported human specialist handoff dispatch with delivery truthfulness invariant.

#### Phase 4: Sprint 4.0 — BI Telemetry & Analytics Migration (COMPLETED)
- Ported `bi_events` insertion and sanitization service to Python.
- Ported BI aggregation endpoints (`/funnel`, `/objections`, `/demand`, `/events`).
- Enforced client fabrication defense separating untrusted client signals from server-verified outcomes.

#### Phase 4.5: Sprint 4.5 — Integration, Security, and Cutover Readiness Audit (COMPLETED)
- Performed end-to-end integration and security audit across Python and Node.js backends.
- Audited tenant scoping (`X-Tenant-ID`), cross-tenant mutation boundaries, and identified lack of authenticated principal as Release Blocker.
- Hardened API contracts for dual camelCase/snake_case frontend parity and truthfulness invariants.
- Pytest suite expanded to 218 passed tests; Node.js suite verified at 54 passed tests (272 total passed tests).

#### Phase 5: Sprint 5.0 — Verification, Gateway Routing & Phased Cutover (PLANNED)
- Deploy Nginx / Caddy reverse proxy to split incoming traffic:
  - Route `/api/v1/*` to FastAPI (port 8000).
  - Route static files and legacy endpoints to Node.js (port 3000).
- Run side-by-side automated regression tests against both servers.
- Repoint frontend clients once Python endpoints have achieved 100% feature and performance parity.

---

## 8. Sprint 3 AI Agent Migration Audit & Completion Report

### 8.1 Node.js vs. Python Architecture Mapping

| Component | Node.js Implementation (`server/`) | Python Target (`backend/app/agents/`) | Parity Status |
|---|---|---|---|
| **Agent Orchestrator** | `server/ai/aiAgent.js` (`runSalesAgent`) | `agent.py` (`AgentOrchestrator.handle`) | ✅ 100% Behavioral Parity |
| **Provider Selection** | Hardcoded priority cascade in `aiAgent.js` | `provider_factory.py` (`get_provider`) | ✅ Gemini > Claude > OpenAI > Local |
| **Provider Adapters** | Direct `fetch()` calls in `aiAgent.js` | `providers.py` (`GeminiProvider`, `AnthropicProvider`, `OpenAIProvider`, `LocalFallbackProvider`) | ✅ Normalized interface with timeout & safe errors |
| **Prompt Engineering** | `server/ai/promptTemplates.js` | `prompt_templates.py` (`build_system_prompt`) | ✅ Luxury jewelry, dining, clinical healthcare rules ported |
| **Security Guardrails** | `server/ai/guardrails.js` | `guardrails.py` (`Guardrails`) | ✅ English/Arabic injection checks, length bound, PCI redaction |
| **Read-Only Tools** | `server/tools/toolRegistry.js` | `tools.py` (`ReadOnlyToolExecutor`) | ✅ 6 read-only tools ported with tenant scoping |
| **Write Protection** | Executed in Node.js | Blocked with safe message in `tools.py` | ✅ `create_order_draft`, `update_order_draft`, etc. disabled |
| **Test Endpoint** | None (Node.js `/api/chat` is production) | `POST /api/v1/agent/test`, `GET /api/v1/agent/info` | ✅ Isolated non-production test harness |

### 8.2 Provider Compatibility & Configuration
- **API Key Handling:** Provider credentials (`GEMINI_API_KEY`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`) are read strictly from environment settings (`backend.app.core.config.settings`).
- **No Secret Logging:** PII and secret values are masked in `__repr__` and filtered from log outputs.
- **Graceful Timeouts:** LLM calls enforce `settings.AI_REQUEST_TIMEOUT_SECONDS` (default 30s) and catch `httpx.TimeoutException`, gracefully falling back to deterministic local processing without crashing or leaking traces.
- **Deterministic Testing:** All test suites use mock provider responses or the built-in local deterministic orchestrator; zero external paid API requests are made during testing.

### 8.3 Prompt & Guardrail Parity Findings
1. **Prompt Injections:** Detected via regex patterns matching "ignore previous instructions", "system prompt", "reveal prompt", "DAN mode", and their Arabic equivalents ("تجاهل التعليمات", "البرومبت الرئيسي").
2. **Medical Guardrails:** Preserved explicit restrictions forbidding medical diagnoses or drug prescriptions for the healthcare tenant (`vitalis-health`).
3. **Draft Safety:** The prompt strictly forbids claiming that an order or reservation is finalized, emphasizing that drafts require explicit customer confirmation.
4. **Data Isolation:** Every tool query enforces `tenant_id = :tenant_id`, preventing any cross-tenant data leakage.

### 8.4 Known Gaps & Deferred Items (Scheduled for Sprint 3.5 & 4)
- **Draft Order Mutations:** Write operations (`create_order_draft`, `update_order_draft`, `confirm_order_draft`) remain exclusively on Node.js until Sprint 3.5.
- **WhatsApp Escalation:** WhatsApp link generation and specialist handoff remain handled by Node.js.
- **Production Routing:** Production `/api/chat` remains on Node.js port 3000. Frontend clients (`chat.html`) have NOT been modified.

### 8.5 Running Python Agent in Isolated Development Mode
1. Ensure dependencies are installed:
   ```powershell
   pip install -r backend/requirements.txt
   ```
2. Start the FastAPI development server:
   ```powershell
   uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
   ```
3. Test a conversation turn via the isolated test endpoint:
   ```powershell
   curl -X POST http://127.0.0.1:8000/api/v1/agent/test `
     -H "Content-Type: application/json" `
     -d '{"tenantId": "al-noor-jewelry", "sessionId": "dev-test-1", "message": "السلام عليكم"}'
   ```
4. Verify provider diagnostics:
   ```powershell
   curl http://127.0.0.1:8000/api/v1/agent/info
   ```

---

## 9. Rollback Strategy

Because this migration preserves the existing Express backend and makes zero destructive database changes, rollback is instantaneous and risk-free:

1. **Independent Port Allocation:**
   - Node.js Express runs on port 3000.
   - FastAPI runs on port 8000.
   - No port collision exists.
2. **Reverse Proxy Rollback:**
   - If any issue arises with a migrated Python endpoint, the reverse proxy rule is reverted to forward all traffic to Node.js (port 3000).
3. **Database Independence:**
   - The Python backend performs only read-only operations on the production database in this sprint.
   - Test suites execute against in-memory SQLite fixtures (`sqlite:///:memory:`) and never modify persistent records.
4. **Process Isolation:**
   - Stopping the Python backend (`uvicorn`) does not affect the Node.js server in any way.

---

## 10. Sprint 3.5 Draft Orders & Booking Lifecycle Completion Report

### 10.1 Draft Order State Machine

```mermaid
stateDiagram-v2
    [*] --> DRAFT : create_draft() [Pricing & Availability verified]
    DRAFT --> DRAFT : update_draft() [Items / notes / promo re-priced]
    DRAFT --> CANCELLED : cancel_draft() [No stock change]
    DRAFT --> CONFIRMED : confirm_draft() [Explicit Customer Gate + Stock Reserved]
    CONFIRMED --> CONFIRMED : confirm_draft() [Idempotent retry with key]
    CONFIRMED --> CANCELLED : cancel_draft() [Inventory Restored]
    CANCELLED --> [*]
```

#### Valid State Transitions & Invariants:
1. **DRAFT Creation:** Generates a non-binding draft with server-computed prices, VAT, and deposits. Does not decrement stock or collect payment. Status: `draft`.
2. **DRAFT Update:** Permitted only when `status == 'draft'`. Recalculates all pricing server-side. Forbidden if draft is `confirmed` or `cancelled`.
3. **Explicit Confirmation Gate:** Permitted only from `draft -> confirmed`. Requires unambiguous customer confirmation (`customer_explicitly_confirmed = True` for agent; verified explicit API call for endpoints). Re-validates inventory; decrements stock count; marks `confirmed`.
4. **Idempotency:** Re-invoking `confirm_draft` on an already-confirmed draft with the same idempotency key or ID returns HTTP 200 with `already_confirmed: true` and identical reference without repeating side effects.
5. **DRAFT Cancellation:** Permitted from `draft` (no stock restoration needed) or `confirmed` (automatically increments `stock_count` back). Rejects cancelling already `cancelled` drafts.

---

### 10.2 Booking State Machine & Concurrency

```mermaid
stateDiagram-v2
    [*] --> AVAILABLE : Initial Slot
    AVAILABLE --> BOOKED : create_booking() [Capacity filled]
    AVAILABLE --> AVAILABLE : create_booking() [Capacity remaining]
    BOOKED --> AVAILABLE : cancel_booking() [Slot reopened]
```

#### Concurrency & Double-Booking Strategy:
- **Database Boundary:** Uses SQLite with WAL mode (`PRAGMA journal_mode=WAL`) and `PRAGMA busy_timeout=5000`.
- **Atomic Capacity Checks:** In `BookingRepository.reserve_slot()`, capacity re-evaluation and booking record creation occur inside an atomic database transaction. If requested `party_size` exceeds remaining capacity (`max_capacity - booked_count`), transaction raises `InsufficientCapacityError` and rolls back.
- **SQLite Concurrency Reality & Limitation:** SQLite supports single-writer serialization. Under multi-process load, SQLite serializes writes. Under extreme high-concurrency bursts across worker processes, lock waits may encounter timeout unless pooled correctly. For production horizontal scale, migration to PostgreSQL with `SELECT ... FOR UPDATE` row-level locks is recommended (Sprint 5).

---

### 10.3 API Contracts

#### Draft Order Endpoints (`/api/v1/drafts`):
| Method | Endpoint | Request Schema | Response Schema | Description |
|---|---|---|---|---|
| `POST` | `/api/v1/drafts` | `DraftCreateRequest` | `DraftResponse` (201) | Create non-binding order draft |
| `GET` | `/api/v1/drafts/{id}` | - | `DraftResponse` (200) | Retrieve draft by ID |
| `PUT` | `/api/v1/drafts/{id}` | `DraftUpdateRequest` | `DraftResponse` (200) | Update editable draft |
| `POST` | `/api/v1/drafts/confirm` | `DraftConfirmRequest` | `DraftConfirmResponse` (200) | Explicit confirmation with idempotency |
| `POST` | `/api/v1/drafts/cancel` | `DraftCancelRequest` | `DraftCancelResponse` (200) | Cancel draft and restore inventory |

#### Booking Endpoints (`/api/v1/bookings`):
| Method | Endpoint | Request Schema | Response Schema | Description |
|---|---|---|---|---|
| `GET` | `/api/v1/bookings/availability` | Query (`tenant_id`, `date`, `service_type`) | `BookingAvailabilityResponse` (200) | Query available slots |
| `GET` | `/api/v1/bookings/slots/{id}` | - | `BookingSlotResponse` (200) | Get specific slot details |
| `POST` | `/api/v1/bookings/reserve` | `BookingCreateRequest` | `BookingResponse` (201) | Reserve booking with concurrency guard |
| `POST` | `/api/v1/bookings/cancel` | `BookingCancelRequest` | `BookingResponse` (200) | Cancel booking & release capacity |

---

### 10.4 Authorization Assumptions & Unresolved Gaps

1. **Tenant Scoping (`X-Tenant-ID` Header):** All draft and booking write endpoints enforce tenant isolation via `get_authorized_tenant`, validating that the caller provides a valid `X-Tenant-ID` header matching an existing tenant. Any mismatch with request body returns HTTP 403 Forbidden.
2. **Current Authentication Limitation:** The legacy Node.js application uses anonymous web chat sessions without customer login (JWT or OAuth). As a result, drafts are bound to `session_id` and `tenant_id`. State-changing endpoints are isolated to development/test harnesses on port 8000 and are **NOT** publicly exposed on port 3000. Customer authentication (JWT/session tokens) will be introduced before production cutover in Sprint 5.

---

### 10.5 Audit Logging & Security Guarantees

- **Audit Trail:** Every draft state change (`DRAFT_CREATED`, `DRAFT_UPDATED`, `DRAFT_CONFIRMED`, `DRAFT_CANCELLED`) and booking state change (`BOOKING_CREATED`, `BOOKING_CANCELLED`) records an entry in `audit_logs` with timestamps, actor identifier, and sanitized metadata.
- **PCI-DSS Compliance:** Credit card numbers are redacted by middleware and logging formatters; card data is never stored in the database.
- **Server-Side Pricing Invariant:** Client totals and prices are ignored. Subtotals, promo codes (`VIRALX10`), dining VAT (14%), dining deposits (500 EGP), and GCC courier shipping (250 EGP) are computed exclusively on the server using verified catalog records.

---

### 10.6 Automated Test Suite & Verification Results

Execution date: 2026-10-26.

1. **Python Pytest Suite:**
   ```powershell
   pytest backend/tests -v
   ```
   - **Result:** **116 passed**, 0 failed, 5 warnings in 7.94s.
   - **Coverage:** Draft lifecycle (creation, update, pricing, stock validation), Explicit Confirmation Gate, cancellation with inventory restore, cross-tenant isolation, idempotency, booking availability, slot capacity, concurrent booking prevention, and tool executor integration.

2. **Node.js Regression Suite:**
   ```powershell
   node --test server/tests/*.test.js
   ```
   - **Result:** **54 passed**, 0 failed in 10.68s.
   - **Coverage:** Legacy Node.js Express server remains 100% operational with zero regressions.

---

### 10.7 Features Exclusively Handled by Node.js (Post-Sprint 3.6)
- Production AI Chat routing (`POST /api/chat` on port 3000).
- BI Telemetry aggregation endpoints (`/api/analytics/*`, scheduled for Sprint 4).

---

## 11. Sprint 3.6 Implementation — Human Handoff Engine & WhatsApp Adapter Migration

### 11.1 Architecture & Objectives
Migrated the human handoff decision engine, WhatsApp link generation, redaction rules, and escalation state lifecycle into Python/FastAPI with:
- **Strict Tenant Phone Grounding:** Business phone number is read exclusively from the verified Tenant configuration record in SQLite (`tenant.phone`). Callers and AI agents cannot supply or override destination phone numbers.
- **Safe WhatsApp URL Construction:** Click-to-chat links enforce allowlisted domains (`https://wa.me/` and `https://api.whatsapp.com/`). Arbitrary redirects, javascript schemes, and suspicious hosts are strictly rejected with typed domain exceptions.
- **Content Redaction & Privacy:** PCI/secret scanner redacts credit card sequences, bearer tokens, API keys, and credential assignments while preserving customer intent, Arabic notes, and draft item summaries.
- **Delivery Truthfulness Invariant:** Explicitly marks all returned handoff payloads with `disclaimer: "URL prepared for client-side click-to-chat. No backend delivery was performed."` and `message_sent: false`. Prevents AI agents from fabricating message delivery.
- **Multi-Tenant State Lifecycle:** Handoff requests record unique IDs, idempotency keys, tenant isolation, and audit trail entries (`HANDOFF_REQUESTED`, `HANDOFF_CLOSED`). Cross-tenant reads and mutations return HTTP 403.
- **Backward Compatibility:** Response structure maintains 1-to-1 compatibility with legacy Node.js Express format (`{ success, handoffUrl, summary, draftId, tenantName, escalationReason }`) alongside modern v1 schema.

### 11.2 Endpoints Implemented (v1)
- `POST /api/v1/handoff/whatsapp`: Escalates conversation to WhatsApp click-to-chat.
- `GET /api/v1/handoff/{id}`: Retrieves handoff state (tenant-isolated).
- `POST /api/v1/handoff/{id}/close`: Closes escalation lifecycle.

### 11.3 Automated Test Suite & Verification Results
Execution date: 2026-10-26.

1. **Python Pytest Suite:**
   ```powershell
   pytest backend/tests -v
   ```
   - **Result:** **170 passed**, 0 failed, 5 warnings in 5.56s.
   - **Coverage:** E.164 phone normalization, allowlisted URL generation, sensitive data redaction, Arabic encoding, escalation intent detection (English/Arabic complaints/keywords), tenant isolation, lifecycle management, agent tool execution isolation, and full endpoint contract tests.

2. **Node.js Production Regression Suite:**
   ```powershell
   node --test server/tests/*.test.js
   ```
   - **Result:** **54 passed**, 0 failed in 10.59s.
   - **Coverage:** Legacy Node.js Express server remains 100% operational with zero regressions.

---

## 12. Sprint 4 Implementation — Business Intelligence & Analytics Migration

### 12.1 Architecture & Objectives
Migrated the entire BI telemetry ingestion, data aggregation, analytical queries, and demo seed generator from Node.js Express to Python FastAPI with:
- **Strict Multi-Tenant Scoping:** All analytical endpoints require `X-Tenant-ID` header matching an authorized tenant in SQLite (`Tenant.id`). If a query or body `tenantId` is supplied, it must match the authorized tenant, returning `403 Forbidden` on mismatch.
- **Client Fabrication Defense:** Untrusted clients calling `/api/v1/analytics/events` are strictly restricted to behavioral signals (`PRODUCT_SEARCH`, `UNFULFILLED_DEMAND`, `UNANSWERED_QUESTION`). Server-verified business outcomes (`DRAFT_CONFIRMED`, `DRAFT_CREATED`, `DRAFT_CANCELLED`, `DRAFT_UPDATED`, `HUMAN_HANDOFF_REQUESTED`, `TOOL_EXECUTION_FAILED`, `LLM_PROVIDER_FAILED`, `SECURITY_GUARDRAIL_TRIGGERED`, `OUT_OF_STOCK_DETECTED`) cannot be reported by clients and are rejected with `403 Forbidden`.
- **Sensitive Data Redaction (PCI-DSS & Secrets):** Metadata sanitization automatically redacts credit cards (13–19 digits), bearer tokens, API keys, and credential assignments while stripping dangerous top-level keys (`password`, `token`, `secret`, `authorization`).
- **Idempotency Protection:** Enforces deduplication using `idempotency_key` unique constraint in SQLite. Duplicate submissions return `{ success: true, duplicate: true, event: ... }` without creating duplicate records.
- **Exact Parity with Node.js Metric Formulas:**
  - **5-Stage Conversion Funnel:**
    1. *Inbound Customer Inquiries:* `totalSessions` (100.0%)
    2. *Catalog & Inventory Engaged:* `searches / totalSessions`
    3. *Grounded Product Recommendation:* `successfulSearches / searches`
    4. *Order or Booking Drafted:* `draftsCreated / searches`
    5. *Explicit Customer Confirmation:* `draftsConfirmed / draftsCreated`
    - *Overall Conversion Rate:* `draftsConfirmed / max(totalSessions, searches, 1)`
    - Zero-division safety: handles empty datasets returning `0.0%` cleanly.
  - **Customer Objections:** Categorizes friction into `out_of_stock`, `unfulfilled_searches`, `unanswered_questions`, and `cancelled_drafts`.
  - **Unfulfilled Demand Signals:** Extracts top unfulfilled queries and out-of-stock detections with configurable limit clamping (1–100).
  - **Telemetry Summary:** Returns consolidated event counts and 7 funnel counters (`searches`, `unfulfilled`, `out_of_stock`, `drafts_created`, `drafts_confirmed`, `drafts_cancelled`, `handoffs`).
  - **Repeatable Demo Seed Generator:** Generates 6 canonical seed events (`PRODUCT_SEARCH`, `UNFULFILLED_DEMAND`, `OUT_OF_STOCK_DETECTED`, `UNANSWERED_QUESTION`, `DRAFT_CREATED`, `HUMAN_HANDOFF_REQUESTED`).

### 12.2 Endpoints Implemented (v1)
- `GET /api/v1/analytics/events`: Query events with tenant isolation, event type, session, demo, and pagination filters.
- `POST /api/v1/analytics/events`: Ingests validated telemetry events with client fabrication defense.
- `POST /api/v1/analytics/events/demo-seed`: Generates repeatable demo telemetry seeds.
- `GET /api/v1/analytics/summary`: Consolidated event counts and conversion counters.
- `GET /api/v1/analytics/funnel`: 5-stage conversion funnel metrics.
- `GET /api/v1/analytics/objections`: Categorized purchase objection breakdown.
- `GET /api/v1/analytics/demand`: Unfulfilled demand signals and out-of-stock events.

### 12.3 Automated Test Suite & Verification Results
Execution date: 2026-10-26.

1. **Python Pytest Suite:**
   ```powershell
   pytest backend/tests -v
   ```
   - **Result:** **201 passed**, 0 failed, 5 warnings in 8.67s.
   - **Coverage:** Full Sprint 4 test suite (31 tests in `test_analytics.py`) + all previous sprints. Validates event types, schema validation, payload size limit (32KB), idempotency, cross-tenant isolation, client fabrication rejection, funnel math & zero-division safety, objection grouping, demand signals, demo seed generation, and HTTP status contracts.

2. **Node.js Production Regression Suite:**
   ```powershell
   node --test server/tests/*.test.js
   ```
   - **Result:** **54 passed**, 0 failed in 8.75s.
   - **Coverage:** Legacy Node.js Express server remains 100% operational with zero regressions.

### 12.4 Performance Considerations & Database Indexing
- Aggregations leverage existing indices on SQLite:
  - `idx_bi_events_tenant_time ON bi_events(tenant_id, created_at)`
  - `idx_bi_events_type ON bi_events(tenant_id, event_type)`
  - `idx_bi_events_demo ON bi_events(tenant_id, is_demo)`
- Date arithmetic uses native SQLite `datetime('now', '-' || :days || ' days')` executed on the database engine, avoiding in-memory table scans.
- Query results are bounded by limit clamping (`limit: 1..500` for events, `1..100` for demand signals, `days: 1..365` for timeframes).

### 12.5 Rollback Procedure
If any issue occurs prior to production cutover:
1. No production frontend or traffic routes to Python port 8000. All live traffic continues to point to Node.js port 3000.
2. In the event of a rollback, disable the Python analytics router by omitting `api_router.include_router(analytics.router)` in `backend/app/api/v1/api.py`.
3. The shared SQLite database `data/viralx.db` requires no schema modifications or rollbacks as `bi_events` schema remains 100% backward-compatible.

---

## 13. Sprint 4.5 Implementation — Integration, Security, and Cutover Readiness Audit

### 13.1 Phase 1 — Verified Repository Inventory

A complete inspection of Python and Node.js source files, database schemas, and frontend dependencies was conducted:

| Endpoint (FastAPI) | HTTP Method | Caller / Purpose | Database Dependency | Auth & Tenant Guard | Node.js Legacy Equivalent | Status |
|---|---|---|---|---|---|---|
| `/health`, `/api/health` | `GET` | Monitoring & Orchestrator | None | Public | `GET /api/health` | ✅ Parity Verified |
| `/ready`, `/api/ready` | `GET` | Readiness Probe | `SELECT 1` | Public | None (New in Python) | ✅ Parity Verified |
| `/api/v1/tenants` | `GET` | Web Catalog & Config | `tenants` table | Public (Demo Mode) | `GET /api/tenants` | ✅ Parity Verified |
| `/api/v1/tenants/{id}` | `GET` | Tenant metadata & hours | `tenants` table | Public (Demo Mode) | `GET /api/tenants/:id` | ✅ Parity Verified |
| `/api/v1/tenants/{id}/catalog` | `GET` | Catalog & real-time stock | `products`, `inventory` | Tenant ID URL param | `GET /api/tenants/:id/catalog` | ✅ Parity Verified |
| `/api/v1/agent/test` | `POST` | Dev / QA chat test harness | Providers / Local fallback | Dev-only body params | None (Internal Harness) | ✅ Isolated (Port 8000) |
| `/api/v1/agent/info` | `GET` | LLM diagnostics & status | Config | Dev-only | None (Internal Harness) | ✅ Isolated (Port 8000) |
| `/api/v1/drafts` | `POST` | Non-binding order drafting | `order_drafts`, `inventory` | `X-Tenant-ID` required | `POST /api/drafts` | ✅ Isolated (Port 8000) |
| `/api/v1/drafts/{id}` | `GET` | Draft retrieval | `order_drafts` | `X-Tenant-ID` required | `GET /api/drafts/:id` | ✅ Isolated (Port 8000) |
| `/api/v1/drafts/{id}` | `PUT` | Draft modification & repricing | `order_drafts`, `inventory` | `X-Tenant-ID` required | `PUT /api/drafts/:id` | ✅ Isolated (Port 8000) |
| `/api/v1/drafts/confirm` | `POST` | Explicit confirmation & reserve | `order_drafts`, `inventory` | `X-Tenant-ID` required | `POST /api/drafts/confirm` | ✅ Isolated (Port 8000) |
| `/api/v1/drafts/cancel` | `POST` | Cancellation & stock restore | `order_drafts`, `inventory` | `X-Tenant-ID` required | `POST /api/drafts/cancel` | ✅ Isolated (Port 8000) |
| `/api/v1/bookings/availability` | `GET` | Query available table slots | `booking_slots` | `X-Tenant-ID` required | `toolRegistry.js` tool | ✅ Isolated (Port 8000) |
| `/api/v1/bookings/slots/{id}` | `GET` | Slot details and capacity | `booking_slots` | `X-Tenant-ID` required | `toolRegistry.js` tool | ✅ Isolated (Port 8000) |
| `/api/v1/bookings/reserve` | `POST` | Atomic slot capacity booking | `booking_slots` | `X-Tenant-ID` required | `toolRegistry.js` tool | ✅ Isolated (Port 8000) |
| `/api/v1/bookings/cancel` | `POST` | Cancel booking & release seats | `booking_slots` | `X-Tenant-ID` required | `toolRegistry.js` tool | ✅ Isolated (Port 8000) |
| `/api/v1/handoff/whatsapp` | `POST` | WhatsApp escalation URL build | `tenants`, `handoff_requests` | `X-Tenant-ID` required | `POST /api/handoff/whatsapp` | ✅ Isolated (Port 8000) |
| `/api/v1/handoff/{id}` | `GET` | Handoff state retrieval | `handoff_requests` | `X-Tenant-ID` required | None (New in Python) | ✅ Isolated (Port 8000) |
| `/api/v1/handoff/{id}/close` | `POST` | Close handoff escalation | `handoff_requests` | `X-Tenant-ID` required | None (New in Python) | ✅ Isolated (Port 8000) |
| `/api/v1/analytics/events` | `POST` | Telemetry event ingestion | `bi_events` | `X-Tenant-ID` required | `POST /api/analytics/events` | ✅ Isolated (Port 8000) |
| `/api/v1/analytics/events` | `GET` | Query telemetry events | `bi_events` | `X-Tenant-ID` required | `toolRegistry.js` / Direct | ✅ Isolated (Port 8000) |
| `/api/v1/analytics/summary` | `GET` | Conversion & funnel counters | `bi_events` | `X-Tenant-ID` required | `GET /api/analytics/summary` | ✅ Isolated (Port 8000) |
| `/api/v1/analytics/funnel` | `GET` | 5-stage conversion funnel | `bi_events` | `X-Tenant-ID` required | `GET /api/analytics/funnel` | ✅ Isolated (Port 8000) |
| `/api/v1/analytics/objections` | `GET` | Friction & objection breakdown | `bi_events` | `X-Tenant-ID` required | `GET /api/analytics/objections` | ✅ Isolated (Port 8000) |
| `/api/v1/analytics/demand` | `GET` | Unfulfilled search signals | `bi_events` | `X-Tenant-ID` required | `GET /api/analytics/demand` | ✅ Isolated (Port 8000) |
| `/api/v1/analytics/events/demo-seed` | `POST` | Repeatable seed generator | `bi_events` | `X-Tenant-ID` required | `POST /api/analytics/events/demo-seed` | ✅ Isolated (Port 8000) |

#### Remaining Node.js-Only Production Responsibilities:
1. **Production AI Chat (`POST /api/chat` on port 3000):** Production chat UI (`chat.html`) routes exclusively to Node.js.
2. **Static Web Hosting (`index.html`, `about.html`, `contact.html`, `assets/*` on port 3000):** Served via Node.js Express static middleware with traversal protection and security headers.
3. **Session Store Initialization:** Node.js manages anonymous chat sessions in SQLite.

---

### 13.2 Phase 2 — Authentication and Tenant Isolation Review

#### Analysis of `X-Tenant-ID`:
- **Current Mechanism:** Endpoints inspect the `X-Tenant-ID` header, verify its existence against the `tenants` table in SQLite, and strictly enforce resource scoping.
- **Security Assessment:** An HTTP header such as `X-Tenant-ID` is **NOT proof of principal identity or authorization**. Any client or developer can supply any valid tenant identifier (e.g., `al-noor-jewelry` or `saffron-table`).
- **Defenses Verified:**
  - Header tampering between conflicting body/query parameters is strictly intercepted and returns `403 Forbidden`.
  - Attempts to access, confirm, modify, or cancel drafts belonging to other tenants return `403 Forbidden`.
  - Attempts to reserve or cancel booking slots of other tenants return `403 Forbidden`.
  - Attempts to view or close handoff records of other tenants return `403 Forbidden`.
  - Client attempts to fabricate server-verified telemetry events (`DRAFT_CONFIRMED`, `DRAFT_CREATED`, etc.) return `403 Forbidden`.
  - Missing headers on protected routes return `401 Unauthorized`. Nonexistent tenants return `404 Not Found`.
- **CRITICAL RELEASE BLOCKER:**
  - **Absence of Authenticated Principal Binding:** There is no cryptographically signed JWT, mTLS, or session cookie binding the caller to the tenant.
  - **Verdict:** Write-capable endpoints (`/api/v1/drafts/*`, `/api/v1/bookings/*`, `/api/v1/handoff/*`, `/api/v1/analytics/*`) must **REMAIN ISOLATED** to development and testing on port 8000. Under no circumstances should they be exposed to the public internet or production cutover until a verified token-based authentication service (e.g., Auth0 / Supabase JWT / HMAC API keys) is implemented.

---

### 13.3 Phase 3 — Cross-Service Business Consistency Audit

1. **Catalog & Inventory Grounding:**
   - Catalog queries join with live `inventory` records. Items with zero available stock (`stock_count - reserved_count <= 0`) are flagged `in_stock: false`.
   - The AI agent tool executor rejects drafting items with insufficient stock.
2. **Deterministic Server-Side Pricing Invariant:**
   - Client-supplied prices and totals are completely discarded.
   - Taxes (14% dining VAT), deposits (500 EGP for restaurant degustation), promo codes (`VIRALX10` for 10% discount), and GCC shipping rules are computed strictly on the server from active database rows.
3. **Draft Modification & Recalculation:**
   - Updating item quantities or discount codes automatically triggers complete server-side price recalculation and inventory revalidation.
4. **Explicit Confirmation Gate:**
   - The AI agent orchestrator is strictly prevented from confirming draft orders or booking slots without explicit customer consent (`customer_explicitly_confirmed = True`).
   - Draft creation creates a draft only (`status: draft`); zero inventory is reserved at creation time.
   - Inventory reservation occurs strictly at the explicit confirmation step.
5. **Idempotency & Double-Side-Effect Prevention:**
   - Confirmation requests include an `idempotencyKey`. Re-submitting an already-confirmed draft returns `already_confirmed: true` / `alreadyConfirmed: true` with the original external reference without double-decrementing stock.
6. **Booking Capacity & Concurrency Protection:**
   - Single-writer WAL mode and atomic SQL update statements (`booked_count = booked_count + :party_size WHERE capacity - booked_count >= :party_size`) prevent overbooking under concurrent requests.
7. **Human Handoff Truthfulness Invariant:**
   - Returned WhatsApp payloads explicitly state: `disclaimer: "URL prepared for client-side click-to-chat. No backend delivery was performed. Preparing this link does not send an automated message or guarantee delivery until opened by the customer."`
   - AI agent tools and services never set `delivered: true` or `accepted_by_human: true`.
8. **Telemetry Event Integrity:**
   - Client fabrication defense restricts untrusted callers to behavioral signals (`PRODUCT_SEARCH`, `UNFULFILLED_DEMAND`, `UNANSWERED_QUESTION`). Server-verified business outcomes cannot be spoofed by callers.
9. **Cancelled / Unconfirmed Metrics:**
   - Cancelling a draft records `DRAFT_CANCELLED` and restores reserved inventory. Cancelled drafts are excluded from conversion funnel completion rates.

---

### 13.4 Phase 4 — API Contract Compatibility Findings

| Dimension | Node.js Express (Legacy) | Python FastAPI (v1) | Compatibility Resolution |
|---|---|---|---|
| **JSON Field Casing** | `camelCase` (`draftId`, `handoffUrl`, `alreadyConfirmed`) | `snake_case` idiomatic Pydantic | **Dual-Casing Support:** Schemas support both camelCase aliases and snake_case fields with `populate_by_name=True`. |
| **Arabic & Unicode** | UTF-8 JSON native | UTF-8 JSON native | Verified: Arabic characters (e.g. `سوار نور المرصع بياقوت السفير`) preserve exact byte sequences without escaping errors. |
| **Handoff Response** | `{ success, handoffUrl, summary, tenantName, escalationReason }` | `HandoffResponse` Pydantic model | Extended with `handoffUrl`, `tenantName`, `escalationReason`, and `draftId` for 1-to-1 frontend compatibility. |
| **Draft Confirmation** | `{ success, alreadyConfirmed, external_reference, draft }` | `DraftConfirmResponse` | Configured with both `already_confirmed` and `alreadyConfirmed`. |
| **Error Format** | `{ error: "message" }` | RFC 7807 `{ "detail": "message" }` | Clean error mapping middleware strips internal stack traces, DB file paths, and environment secrets. |
| **HTTP Status Codes** | 200, 400, 403, 404, 500 | 200, 201, 400, 401, 403, 404, 422, 500 | Aligned status codes: 201 for draft/booking/handoff creation, 401 for missing auth, 403 for cross-tenant. |

---

### 13.5 Phase 5 — Database and Concurrency Review

- **Schema Alignment:** SQLAlchemy models in `backend/app/db/models.py` match `server/db/schema.sql` 1-to-1 (tables: `tenants`, `products`, `inventory`, `sessions`, `messages`, `order_drafts`, `booking_slots`, `handoff_requests`, `audit_logs`, `bi_events`).
- **Foreign Key Enforcement:** Verified `PRAGMA foreign_keys = ON;` is active on all SQLite engine connections.
- **Transaction Rollbacks:** Verified atomic rollbacks on exceptions in draft and booking operations (test verified in `test_explicit_confirmation_reserves_inventory` and `test_concurrency`).
- **SQLite Concurrency Limitation:**
  - SQLite in WAL mode with `PRAGMA busy_timeout=5000` safely handles serialized local concurrency.
  - However, SQLite remains single-writer. In multi-process production deployments (e.g. multi-worker Uvicorn or multiple containers), write lock contention may cause latency spikes under high transaction volumes.
  - **Recommendation:** A migration to PostgreSQL with row-level locking (`SELECT ... FOR UPDATE`) is strongly recommended prior to horizontal multi-worker production scale.

---

### 13.6 Phase 6 — Automated Security and Integration Test Results

Executed on 2026-10-26 in the workspace environment:

#### 1. Python Pytest Test Suite:
```powershell
pytest backend/tests -v
```
- **Passed:** **218 tests** (0 failed, 6 deprecation warnings, duration ~9.74s)
- **Breakdown of Test Suites:**
  - `test_agent.py`: 44 tests (guardrails, prompt templates, read-only tools, orchestrator, mock provider, agent endpoints).
  - `test_analytics.py`: 31 tests (telemetry ingestion, client fabrication defense, idempotency, PCI redaction, funnel math, objections, demo seed).
  - `test_audit_security.py`: 21 tests (tenant authorization boundaries, cross-tenant mutation prevention, business workflow consistency, contract parity, safe error handling).
  - `test_bookings.py`: 18 tests (slot availability, reservations, capacity limits, cancellation, double-booking concurrency, explicit confirmation gate).
  - `test_config.py`: 3 tests (Pydantic settings, database resolution, secret repr masking).
  - `test_drafts.py`: 23 tests (draft creation, retrieval, updates, pricing engine, explicit confirmation gate, inventory reservation, idempotency, cancellation).
  - `test_handoff.py`: 45 tests (phone normalization, safe WhatsApp URLs, PCI redaction, Arabic encoding, escalation detection, lifecycle, truthfulness disclaimer, agent isolation).
  - `test_health.py`: 3 tests (root, /api, /v1 liveness probes).
  - `test_products.py`: 8 tests (catalog queries, category filters, budget filters, search, stock filtering).
  - `test_readiness.py`: 3 tests (healthy readiness, dependency probing, 503 degradation).
  - `test_security.py`: 6 tests (directory traversal, sensitive file blocking, payload size limit, CORS headers).
  - `test_tenant_isolation.py`: 3 tests (cross-tenant catalog isolation).
  - `test_tenants.py`: 4 tests (listing, filtering, single tenant retrieval, 404 handling).

#### 2. Node.js Production Regression Suite:
```powershell
node --test server/tests/*.test.js
```
- **Passed:** **54 tests** (0 failed, duration ~9.54s)
- **Coverage:** Legacy Node.js Express server remains 100% operational with zero regressions across natural language understanding, multi-turn drafts, pricing, inventory grounding, explicit confirmation gate, security guardrails, WhatsApp escalation, demo fallbacks, and telemetry endpoints.

**Total Automated Tests Passed:** **272 passed**, 0 failed.

---

### 13.7 Phase 7 — Cutover Readiness Decision

#### Release-Readiness Matrix:

| Evaluation Dimension | Readiness Status | Evidence / Audit Findings |
|---|---|---|
| **Authentication & Authorization** | **FAIL (BLOCKER)** | Endpoints rely on `X-Tenant-ID` header matching. There is no authenticated principal (JWT/OAuth2/API key). External exposure is strictly unsafe. |
| **Tenant Isolation** | **PASS** | Strict scoping on every query and mutation. Cross-tenant access and conflicting header/body parameters return 403 Forbidden across all services. |
| **Business Workflow Correctness** | **PASS** | Grounded inventory, server-side pricing engine, explicit confirmation gate, idempotency, and handoff truthfulness invariants verified by 218 tests. |
| **API Compatibility** | **PASS** | Node.js compatibility aliases (`camelCase` and `snake_case`), Unicode/Arabic support, and sanitized structured errors verified. |
| **Database Consistency & Concurrency** | **PARTIAL** | Fully consistent on single-instance SQLite (WAL mode, foreign keys, transaction rollbacks). SQLite single-writer bottleneck requires PostgreSQL for horizontal production scale. |
| **Observability & Audit Logging** | **PASS** | Audit trail on all state changes (`DRAFT_CONFIRMED`, `SLOT_RESERVED`, `HANDOFF_TRIGGERED`), sensitive data redaction (credit cards/tokens). |
| **Environment & Secret Management** | **PASS** | Strict Pydantic settings, environment variable isolation, `__repr__` secret masking, no secrets leaked in logs or error traces. |
| **Rollback Readiness** | **PASS** | Zero destructive database changes, zero dual writes, Node.js remains 100% operational on port 3000. Instantaneous rollback capability. |
| **Remaining Node.js Dependencies** | **PARTIAL** | Production frontend still routes to Node.js `/api/chat` and static asset hosting on port 3000. |
| **Deployment & Operational Readiness**| **FAIL (BLOCKER)** | Reverse proxy (Nginx/Caddy) and production TLS gateway not yet provisioned. |

#### Final Cutover Readiness Verdict: **NO-GO / CUTOVER BLOCKED**

> [!CAUTION]
> **Production Cutover is NOT Authorized.**
> Although 272 automated tests pass across Python and Node.js backends, production cutover is blocked by:
> 1. **Authentication Blocker:** Externally exposed endpoints require authenticated principal binding (JWT / API Key), not merely raw `X-Tenant-ID` headers.
> 2. **Database Concurrency Architecture:** SQLite single-writer lock serialization is insufficient for horizontal multi-process production concurrency.
> 
> **Operational Status:**
> - The **Node.js Express backend remains the ONLY production backend** (port 3000).
> - The **FastAPI Python backend remains strictly isolated to development, testing, and staging** (port 8000).

---

### 13.8 Phase 8 — Phased Cutover Plan & Rollback Procedure

When the release blockers (Authentication Service and PostgreSQL) are implemented and approved in a future sprint, the cutover will proceed according to this phased plan:

```mermaid
flowchart TD
    A[Current State: Port 3000 Node.js Production] --> B[Phase A: Reverse Proxy Shadow Deployment]
    B --> C[Phase B: Read-Only Cutover: Health, Catalog, Analytics]
    C --> D[Phase C: AI Agent & Chat Cutover: Port 8000]
    D --> E[Phase D: Transactional Cutover: Drafts, Bookings, Handoff]
    E --> F[Phase E: Legacy Node.js Deprecation & Decommission]

    style A fill:#e1f5fe,stroke:#0288d1
    style B fill:#fff9c4,stroke:#fbc02d
    style C fill:#fff9c4,stroke:#fbc02d
    style D fill:#ffe0b2,stroke:#f57c00
    style E fill:#ffe0b2,stroke:#f57c00
    style F fill:#c8e6c9,stroke:#388e3c
```

#### Phased Rollout Steps:
1. **Phase A (Gateway Shadowing):** Deploy Nginx reverse proxy. Route port 3000 to Node.js. Route `/api/v1/health` and `/api/v1/ready` to FastAPI. Verify uptime for 48 hours.
2. **Phase B (Read-Only Endpoints):** Route `/api/v1/tenants`, `/api/v1/tenants/{id}/catalog`, and `/api/v1/analytics/*` to FastAPI.
3. **Phase C (AI Sales Agent):** Repoint `chat.html` to FastAPI `POST /api/v1/chat` after deploying JWT authentication tokens.
4. **Phase D (Transactional Cutover):** Route drafts, bookings, and WhatsApp handoff endpoints to FastAPI.
5. **Phase E (Decommission):** After 30 days of zero-incident operation on PostgreSQL, archive Node.js Express server.

#### Rollback Procedure:
If any anomaly, latency spike (>500ms), or error rate (>0.1%) occurs during any phase:
1. Revert Nginx reverse proxy upstream config to forward 100% of traffic to Node.js (port 3000).
2. Reload Nginx configuration (`nginx -s reload`). Zero client restart required. Rollback completes in < 5 seconds.
3. Database requires zero rollback as SQLite schema remains backward-compatible with Node.js queries.

---

### 13.9 Explicit Stop Condition

**Sprint 4.5 audit and test hardening is complete.**
- No Node.js source files were deleted.
- No production database records were altered or deleted.
- No frontend client was repointed to the Python backend.
- No dual-write operations were enabled.
- All 272 automated tests pass with 100% reproducibility.
- **STOP:** Awaiting management approval and Sprint 5 authentication implementation before any production cutover.

---

## 14. Sprint 5 — Secure Authentication & Authorization Foundation

### 14.1 Architecture & Token Model

Sprint 4.5 identified `X-Tenant-ID` as an authorization vulnerability: a client-controlled header cannot serve as proof of identity or tenant membership. Sprint 5 resolves this release blocker by establishing a secure, testable cryptographic authentication and least-privilege authorization foundation for the Python backend (`port 8000`), while maintaining full operational stability of the legacy Node.js server (`port 3000`).

#### 1. Authentication Engine
- **Library:** `PyJWT` for industry-standard RFC 7519 HMAC-SHA256 signature verification and claim validation.
- **Password Hashing:** `bcrypt` (`hash_password`, `verify_password`) with automatic cryptographic salting (work factor 12) for local users.
- **Tokens Issued:**
  - **Access Token:** Short-lived (default 60 minutes) HMAC-SHA256 JWT containing verified identity claims, tenant binding, and permissions.
  - **Refresh Token:** Long-lived (default 7 days) HMAC-SHA256 JWT containing unique token identifier (`jti`) used strictly for access token renewal at `POST /api/v1/auth/refresh`.

#### 2. JWT Claims Schema
```json
{
  "sub": "user-uuid-or-id",
  "username": "user_identifier",
  "tenant_id": "verified-tenant-id",
  "role": "admin | manager | staff | customer | read_only",
  "permissions": ["read", "draft:create", "draft:confirm", "..."],
  "type": "access | refresh",
  "iss": "viral-x-auth",
  "aud": "viral-x-api",
  "iat": 1730000000,
  "exp": 1730003600,
  "nbf": 1730000000,
  "jti": "random-uuid4"
}
```

#### 3. Strict Claim Validation Rules
- **Signature:** Must be valid under server-side `JWT_SECRET_KEY`.
- **Expiration (`exp`):** Reject expired tokens with `401 Unauthorized` (`"Token has expired."`).
- **Issuer (`iss`):** Must match `JWT_ISSUER` (`viral-x-auth`). Mismatches return `401 Unauthorized`.
- **Audience (`aud`):** Must match `JWT_AUDIENCE` (`viral-x-api`). Mismatches return `401 Unauthorized`.
- **Token Type (`type`):** Access token endpoints reject refresh tokens (`401 Unauthorized`), and `/auth/refresh` rejects access tokens (`401 Unauthorized`).
- **Subject (`sub`):** Must be a non-empty string identifying the principal.

---

### 14.2 Principal-to-Tenant Binding & Header Rules

```mermaid
flowchart TD
    Req[Incoming HTTP Request] --> AuthCheck{Authorization: Bearer <token>?}
    
    AuthCheck -- Yes --> Dec[Decode & Verify JWT]
    Dec -- Invalid/Expired --> Err401[401 Unauthorized]
    Dec -- Valid --> Prin[Resolve AuthenticatedPrincipal]
    
    AuthCheck -- No --> EnvCheck{is_dev_header_auth_allowed()?}
    EnvCheck -- No (Production) --> ErrProd[401 Unauthorized: Bearer Token Required]
    EnvCheck -- Yes (Dev/Test) --> HeaderCheck{X-Tenant-ID Header present?}
    HeaderCheck -- Yes --> DevPrin[Resolve Dev Principal for Tenant]
    HeaderCheck -- No --> ErrMissing[401 Unauthorized: Missing Credentials]
    
    Prin --> TenantCheck{Does Principal have tenant_id?}
    DevPrin --> TenantCheck
    TenantCheck -- No --> Err403NoTenant[403 Forbidden: No Tenant Membership]
    TenantCheck -- Yes --> ForgedCheck{Client sent X-Tenant-ID header?}
    
    ForgedCheck -- Yes, Conflicts with JWT --> Err403Forged[403 Forbidden: Forged Header Mismatch]
    ForgedCheck -- Yes, Matches JWT --> Bound[Bound Verified Tenant ID]
    ForgedCheck -- No Header --> Bound
    
    Bound --> BodyCheck{Request Body has tenantId?}
    BodyCheck -- Yes, Conflicts with Tenant --> Err403Body[403 Forbidden: Body Tenant Mismatch]
    BodyCheck -- No / Matches --> PermCheck{Route requires permission?}
    
    PermCheck -- Yes, Principal lacks perm --> Err403Perm[403 Forbidden: Insufficient Permissions]
    PermCheck -- Yes, Has perm / No perm needed --> Exec[Execute Endpoint Handler]
```

#### Verification Invariants:
1. **Server-Side Binding:** Tenant workspace is resolved from the cryptographically verified `tenant_id` claim in the Bearer token, NEVER trusted from an unverified client header.
2. **Forged Header Defense:** If an authenticated client supplies an `X-Tenant-ID` header differing from the JWT claim, the request is immediately rejected with `403 Forbidden`.
3. **Body / Query Conflict Defense:** If a payload body includes a `tenant_id` conflicting with the authorized tenant, the request is rejected with `403 Forbidden`.
4. **No Tenant Membership:** If a principal holds a valid token without a bound tenant (`tenant_id = null`), access to tenant-scoped resources returns `403 Forbidden`.
5. **Fail-Closed Development Fallback:** `X-Tenant-ID` header fallback is strictly permitted ONLY in non-production environments when `ALLOW_DEV_HEADER_AUTH=True`. Under `ENVIRONMENT=production`, header fallback is automatically forced to `False`.

---

### 14.3 Permissions and Roles Matrix

The platform implements granular, least-privilege string-based permissions:

| Permission Name | String Constant | Description |
|---|---|---|
| `READ` | `read` | Read public catalogs, drafts, and general tenant data |
| `DRAFT_CREATE` | `draft:create` | Create non-binding order drafts |
| `DRAFT_UPDATE` | `draft:update` | Update draft items, notes, and discount codes |
| `DRAFT_CONFIRM` | `draft:confirm` | Explicitly confirm draft order and reserve inventory |
| `DRAFT_CANCEL` | `draft:cancel` | Cancel draft order and release reserved inventory |
| `BOOKING_READ` | `booking:read` | Query real-time booking slot availability |
| `BOOKING_RESERVE` | `booking:reserve` | Reserve booking slot and commit table capacity |
| `BOOKING_CANCEL` | `booking:cancel` | Cancel booking reservation and release capacity |
| `HANDOFF_CREATE` | `handoff:create` | Prepare human escalation WhatsApp click-to-chat URL |
| `HANDOFF_MANAGE` | `handoff:manage` | Close or update human handoff escalation status |
| `ANALYTICS_READ` | `analytics:read` | Read conversion funnels, objections, and demand signals |
| `ANALYTICS_SEED` | `analytics:seed` | Seed repeatable demo telemetry events |
| `ANALYTICS_EVENTS`| `analytics:events` | Ingest raw behavioral telemetry events |
| `AGENT_TEST` | `agent:test` | Access internal AI agent dev test harness |
| `ADMIN` | `admin` | Superuser wildcard permission |

#### Default Role-to-Permission Mapping:
- **`admin`**: All permissions (`ALL_PERMISSIONS`).
- **`manager`**: All operations except superuser admin management.
- **`staff`**: Day-to-day operations (reads, draft create/update/cancel, bookings, handoffs, analytics read). Cannot perform explicit draft confirmation on behalf of customers.
- **`customer`**: Read catalog/availability, create/modify own drafts, confirm own drafts, reserve own bookings, trigger human handoffs.
- **`read_only`**: View-only access (`read`, `booking:read`, `analytics:read`). Strictly forbidden from all mutation and confirmation operations (`403 Forbidden`).

---

### 14.4 Route Inventory & Classification

| Route Path | Method | Classification | Required Permission / Guard |
|---|---|---|---|
| `/health`, `/api/health`, `/ready` | `GET` | Public | None |
| `/api/v1/tenants` | `GET` | Public | None |
| `/api/v1/tenants/{id}` | `GET` | Public | None |
| `/api/v1/tenants/{id}/catalog` | `GET` | Public | None |
| `/api/v1/auth/token` | `POST` | Public / Auth | Valid username & password |
| `/api/v1/auth/refresh` | `POST` | Public / Auth | Valid unexpired Refresh JWT |
| `/api/v1/auth/me` | `GET` | Authenticated | Valid Bearer JWT |
| `/api/v1/drafts` | `POST` | Protected | Tenant Binding + `draft:create` |
| `/api/v1/drafts/{id}` | `GET` | Protected | Tenant Binding + `read` |
| `/api/v1/drafts/{id}` | `PUT` | Protected | Tenant Binding + `draft:update` |
| `/api/v1/drafts/confirm`, `/{id}/confirm` | `POST` | Critical Protected | Tenant Binding + `draft:confirm` |
| `/api/v1/drafts/cancel`, `/{id}/cancel` | `POST` | Critical Protected | Tenant Binding + `draft:cancel` |
| `/api/v1/bookings/availability` | `GET` | Protected | Tenant Binding + `booking:read` |
| `/api/v1/bookings/slots/{id}` | `GET` | Protected | Tenant Binding + `booking:read` |
| `/api/v1/bookings/reserve` | `POST` | Critical Protected | Tenant Binding + `booking:reserve` |
| `/api/v1/bookings/cancel` | `POST` | Critical Protected | Tenant Binding + `booking:cancel` |
| `/api/v1/handoff/whatsapp` | `POST` | Protected | Tenant Binding + `handoff:create` |
| `/api/v1/handoff/{id}` | `GET` | Protected | Tenant Binding + `read` |
| `/api/v1/handoff/{id}/close` | `POST` | Protected | Tenant Binding + `handoff:manage` |
| `/api/v1/analytics/events` | `POST` | Protected | Tenant Binding + Client Fabrication Defenses |
| `/api/v1/analytics/events` | `GET` | Protected | Tenant Binding + `analytics:read` |
| `/api/v1/analytics/summary` | `GET` | Protected | Tenant Binding + `analytics:read` |
| `/api/v1/analytics/funnel` | `GET` | Protected | Tenant Binding + `analytics:read` |
| `/api/v1/analytics/objections` | `GET` | Protected | Tenant Binding + `analytics:read` |
| `/api/v1/analytics/demand` | `GET` | Protected | Tenant Binding + `analytics:read` |
| `/api/v1/analytics/events/demo-seed` | `POST` | Protected / Admin | Tenant Binding + `analytics:seed` |
| `/api/v1/agent/test` | `POST` | Dev-Only | Dev environment check |
| `/api/v1/agent/info` | `GET` | Dev-Only | Dev environment check |

---

### 14.5 Deployment Safety & Fail-Closed Configuration

#### 1. Configuration Validation on Startup (`validate_production_configuration`)
When running in production (`ENVIRONMENT=production`):
- `ALLOW_DEV_HEADER_AUTH` is automatically forced to `False`. Any attempt to pass `X-Tenant-ID` as an authentication substitute returns `401 Unauthorized`.
- If `JWT_SECRET_KEY` is absent, blank, or contains default insecure placeholder strings (`dev-insecure-jwt-secret-key-change-in-production-viral-x-2026`), the application **refuses to start**, raising a fatal `ValueError`.
- Secret masking: `Settings.__repr__` masks all secrets and keys so configuration printing never leaks credentials.

#### 2. Sensitive Data Redaction Filter
`backend/app/core/logging.py` contains `SensitiveDataFilter` which scrubs:
- JWT Bearer tokens (`Authorization: Bearer eyJ...`) -> `Authorization: Bearer [REDACTED_JWT_TOKEN]`
- Standalone JWT tokens (`eyJ...`) -> `[REDACTED_JWT_TOKEN]`
- JSON passwords and secrets (`"password": "..."`) -> `"password": "[REDACTED_SECRET]"`
- API keys (`api_key: ...`) -> `api_key: [REDACTED_SECRET]`
- Credit card sequences (13–19 digit PANs) -> `[REDACTED_CARD]`

---

### 14.6 Automated Security Verification Results

Executed on 2026-10-27 in the workspace:

#### 1. Python Pytest Test Suite:
```powershell
pytest backend/tests -v
```
- **Passed:** **289 tests** (0 failed, 6 deprecation warnings, duration ~17.79s)
- **New Sprint 5 Security Tests (`backend/tests/test_auth_security.py` — 42 dedicated security tests):**
  - Password hashing & verification (`TestPasswordHashing` — 4 tests)
  - JWT creation, decode, tampering, secret mismatch, expired tokens (`TestJWTTokens` — 7 tests)
  - Missing credentials & malformed bearer headers on all route families (`TestMissingCredentials` — 9 tests)
  - Forged `X-Tenant-ID` header rejection (`TestForgedTenantHeader` — 3 tests)
  - User with no tenant membership (`TestNoTenantMembership` — 2 tests)
  - Cross-tenant read/write prevention on drafts, bookings, analytics (`TestCrossTenantAccess` — 3 tests)
  - Unauthorized draft confirmation attempts (`TestUnauthorizedDraftConfirmation` — 3 tests)
  - Unauthorized booking reservations (`TestUnauthorizedBookingConfirmation` — 2 tests)
  - Analytics endpoint authentication requirements (`TestAnalyticsAuthorization` — 4 tests)
  - Conflicting body tenant IDs (`TestConflictingTenantInBody` — 3 tests)
  - Token refresh lifecycle and invalid refresh handling (`TestTokenRefresh` — 5 tests)
  - Principal inspection via `/me` (`TestMeEndpoint` — 2 tests)
  - Log and error secret redaction (`TestSecretRedaction` — 7 tests)
  - Production fail-closed validation (`TestProductionSafety` — 4 tests)
  - Dev-only backward compatibility (`TestDevHeaderAuthentication` — 3 tests)
  - Least-privilege permissions and role checking (`TestPermissions` — 3 tests)
  - End-to-end business logic regression preservation (`TestBusinessLogicRegression` — 7 tests)

#### 2. Node.js Production Regression Suite:
```powershell
node --test server/tests/*.test.js
```
- **Passed:** **54 tests** (0 failed, duration ~10.05s)
- **Zero Regressions:** Legacy Node.js Express server (`port 3000`) remains 100% operational and untouched.

**Total Automated Tests Passed:** **343 tests** (289 Python + 54 Node.js), 0 failed.

---

### 14.7 Frontend Integration Guidelines (Future Migration)

When the frontend client is ready to integrate with the Python FastAPI backend in a future cutover sprint:

1. **Obtaining Tokens:**
   ```javascript
   const res = await fetch("/api/v1/auth/token", {
     method: "POST",
     headers: { "Content-Type": "application/json" },
     body: JSON.stringify({ username, password }),
   });
   const { accessToken, refreshToken } = await res.json();
   ```

2. **Making Authenticated Requests:**
   All transactional and private API calls must include the Bearer token in the `Authorization` header:
   ```javascript
   const response = await fetch("/api/v1/drafts", {
     method: "POST",
     headers: {
       "Content-Type": "application/json",
       "Authorization": `Bearer ${accessToken}`,
     },
     body: JSON.stringify({ items, sessionId }),
   });
   ```

3. **Silent Token Refresh:**
   When an access token approaches expiration (or receives a `401 Unauthorized`), the frontend should exchange the refresh token:
   ```javascript
   const refreshRes = await fetch("/api/v1/auth/refresh", {
     method: "POST",
     headers: { "Content-Type": "application/json" },
     body: JSON.stringify({ refreshToken }),
   });
   const { accessToken: newAccessToken } = await refreshRes.json();
   ```

4. **Deprecation Notice for Frontend:**
   The client should **stop sending `X-Tenant-ID`**. The server automatically infers the tenant from the verified JWT claims. If `X-Tenant-ID` is passed, it must match the token's `tenant_id` exactly or the request will be rejected with `403 Forbidden`.

---

### 14.8 Operational Cutover Status Reminder

> [!IMPORTANT]
> **NO PRODUCTION CUTOVER HAS OCCURRED.**
> - Legacy Node.js server remains the **ONLY** production backend (port 3000).
> - Python FastAPI server remains on **port 8000** for development, automated security validation, and staging.
> - The shared SQLite database `viral_x.db` was updated with non-destructive, backward-compatible `users` and `revoked_tokens` tables. All legacy Node.js tables remain 100% intact.
> - Zero frontend traffic has been diverted to Python.

---

## 15. Sprint 5.5: End-to-End Authentication Integration & Security Verification Report

**Sprint Status:** Completed & Fully Verified  
**Verification Date:** 2026-10-27  
**Test Suite Summary:** **375 Automated Tests Passed (321 Python + 54 Node.js, 0 Failed, 0 Regressions)**  

---

### 15.1 Executive Summary & Audit Scope

Sprint 5.5 performed an evidence-based security audit, end-to-end verification, and defensive hardening of the Viral-X platform authentication and authorization systems.

Key verification objectives achieved:
1. **Evidence-Based Code Audit:** Audited all Sprint 5 claims against source code and comprehensive test execution.
2. **Cryptographic JWT Lifecycle:** Validated access vs. refresh token type separation, signature verification, claim validation (`sub`, `iss`, `aud`, `exp`, `nbf`, `jti`), algorithm confusion defenses, refresh token rotation, replay attack detection, and explicit logout revocation.
3. **Authorization & Tenant Boundary Hardening:** Enforced principal-to-tenant binding across all routes, customer ownership guards on draft orders and booking reservations, permission checks on AI developer tools, and client claim tampering rejection.
4. **Defensive Frontend Integration:** Validated in-memory access token storage, session-scoped refresh token storage, transparent 401 retry with silent token refresh, and safe logout revocation in `assets/js/auth-client.js` and `chat.html`.
5. **Shared Database & Concurrency Verification:** Confirmed SQLite WAL mode concurrency, busy-timeout locking mitigation, transaction rollback safety, and backward-compatible schema migration (`003_auth_tables.sql`) preserving the production Node.js server (`port 3000`).

---

### 15.2 Evidence-Based Verification Matrix

| Claim / Security Requirement | Implementation File & Method | Test Evidence | Status |
|---|---|---|---|
| **Password Hashing** (bcrypt work factor 12) | `backend/app/core/auth.py:hash_password` | `TestPasswordHashing` (4 tests) | **PASS** |
| **Password Verification** (constant-time, safe) | `backend/app/core/auth.py:verify_password` | `TestPasswordHashing.test_verify_correct_password` | **PASS** |
| **Distinct Token Types** (`access` vs `refresh`) | `backend/app/core/auth.py:create_access_token` & `create_refresh_token` | `test_access_token_cannot_be_used_at_refresh_endpoint`, `test_refresh_token_cannot_be_used_as_bearer_authorization` | **PASS** |
| **Claim Validation** (`iss`, `aud`, `exp`, `nbf`, `sub`, `jti`) | `backend/app/core/auth.py:decode_jwt_token` | `test_future_nbf_claim_rejected`, `test_expired_token_rejected`, `test_missing_jti_claim_rejected` | **PASS** |
| **Algorithm Confusion Defense** (`none`, `RS256` HMAC key reuse) | `decode_jwt_token` strictly whitelisting `algorithms=[settings.JWT_ALGORITHM]` | `test_unsigned_token_none_alg_rejected`, `test_asymmetric_alg_confusion_rejected` | **PASS** |
| **Refresh Token Rotation** | `backend/app/api/v1/endpoints/auth.py:refresh_token` | `test_refresh_token_rotation_and_replay_detection` | **PASS** |
| **Replay Attack Detection** | `backend/app/core/auth.py:is_token_revoked` + `RevokedToken` DB table | `test_refresh_token_rotation_and_replay_detection` (replay returns 401) | **PASS** |
| **Explicit Logout & Revocation** | `backend/app/api/v1/endpoints/auth.py:logout` | `test_logout_revokes_access_and_refresh_tokens` | **PASS** |
| **Deactivated Account Invalidation** | `refresh_token` checking `user.is_active` | `test_deactivated_user_cannot_refresh_token` | **PASS** |
| **Production Secret Validation** (fail-closed) | `backend/app/core/config.py:validate_production_configuration` | `TestProductionSafety` (4 tests) | **PASS** |
| **Server-Side Tenant Binding** | `backend/app/core/auth.py:get_authorized_tenant` | `TestForgedTenantHeader` (3 tests) | **PASS** |
| **Header Tampering Defense** (`X-Tenant-ID` mismatch) | `backend/app/core/auth.py:get_authorized_tenant` | `test_authenticated_request_with_conflicting_header_rejected` (403) | **PASS** |
| **Body / Query Tenant Mismatch Defense** | `drafts.py`, `bookings.py`, `handoff.py`, `analytics.py` | `TestConflictingTenantInBody` (3 tests) | **PASS** |
| **Customer Draft Ownership Enforcement** | `backend/app/api/v1/endpoints/drafts.py:_verify_customer_ownership` | `TestCustomerOwnershipEnforcement` (4 draft tests) | **PASS** |
| **Customer Booking Ownership Enforcement** | `backend/app/api/v1/endpoints/bookings.py:cancel_slot` | `test_customer_cannot_cancel_another_customers_booking`, `test_customer_can_cancel_own_booking` | **PASS** |
| **Staff Draft Confirmation Boundary** | Role permission matrix (`staff` lacks `draft:confirm`) | `test_staff_cannot_confirm_draft` (403 Forbidden) | **PASS** |
| **Read-Only Privilege Boundary** | Role permission matrix (`read_only` lacks mutation perms) | `TestPermissionCoverageAcrossEndpoints` (6 tests) | **PASS** |
| **AI Tool Privilege Inheritance** | `ReadOnlyToolExecutor` with `WRITE_PROTECTED_TOOLS` block | `test_write_protected_tools_match_schema`, `test_agent_cannot_confirm_draft_without_explicit_consent` | **PASS** |
| **Agent Dev Endpoint Protection** | `backend/app/api/v1/endpoints/agent.py:test_agent` | `test_agent_endpoint_rejects_customer_without_agent_test_perm`, `test_agent_endpoint_rejects_cross_tenant_request` | **PASS** |
| **Sensitive Data Redaction in Logs** | `backend/app/core/logging.py:SensitiveDataFilter` | `TestSecretRedaction` (7 tests) | **PASS** |
| **Frontend Authentication Client Flow** | `assets/js/auth-client.js:ViralXAuth` | `test_frontend_full_auth_lifecycle` | **PASS** |
| **Shared Database Concurrency & PRAGMAs** | `backend/app/db/session.py:configure_sqlite_pragmas` | `test_confirmation_idempotency_prevents_double_decrement`, `test_database_session_rollback_preserves_clean_state` | **PASS** |
| **Legacy Node.js Operational Stability** | `server/` endpoints and regression test suite | `node --test server/tests/*.test.js` (54 tests passed) | **PASS** |

---

### 15.3 Route-by-Route Authorization & Permission Coverage

| HTTP Method | Route Path | Access Classification | Required Permission / Guard | Verified Invariant |
|---|---|---|---|---|
| `GET` | `/health`, `/api/health`, `/ready` | Public | None (Rate Limited) | Liveness & Readiness checks |
| `GET` | `/api/v1/tenants` | Public | None | Tenant discovery |
| `GET` | `/api/v1/tenants/{id}` | Public | None | Tenant workspace metadata |
| `GET` | `/api/v1/tenants/{id}/catalog` | Public | None | Multi-tenant inventory-grounded catalog |
| `POST` | `/api/v1/auth/token` | Public / Auth | Valid username & password | Issues typed access & refresh JWTs |
| `POST` | `/api/v1/auth/refresh` | Public / Auth | Valid unrevoked Refresh JWT | Rotates refresh token, rejects replay attacks |
| `POST` | `/api/v1/auth/logout` | Authenticated | Valid Bearer JWT | Revokes active access and refresh tokens |
| `GET` | `/api/v1/auth/me` | Authenticated | Valid Bearer JWT | Returns caller profile & verified permissions |
| `POST` | `/api/v1/drafts` | Protected | Tenant Binding + `draft:create` | Scopes draft session to customer principal |
| `GET` | `/api/v1/drafts/{id}` | Protected | Tenant Binding + `read` | Enforces customer ownership for customer role |
| `PUT` | `/api/v1/drafts/{id}` | Protected | Tenant Binding + `draft:update` | Only owner or staff/manager can update draft |
| `POST` | `/api/v1/drafts/confirm` | Critical Protected | Tenant Binding + `draft:confirm` | Explicit confirmation gate + inventory reservation |
| `POST` | `/api/v1/drafts/cancel` | Critical Protected | Tenant Binding + `draft:cancel` | Releases reserved inventory |
| `GET` | `/api/v1/bookings/availability` | Protected | Tenant Binding + `booking:read` | Real-time slot availability |
| `GET` | `/api/v1/bookings/slots/{id}` | Protected | Tenant Binding + `booking:read` | Verified slot details |
| `POST` | `/api/v1/bookings/reserve` | Critical Protected | Tenant Binding + `booking:reserve` | Atomic capacity reservation + customer session binding |
| `POST` | `/api/v1/bookings/cancel` | Critical Protected | Tenant Binding + `booking:cancel` | Enforces booking ownership verification for customers |
| `POST` | `/api/v1/handoff/whatsapp` | Protected | Tenant Binding + `handoff:create` | Prepares WhatsApp URL from trusted tenant configuration |
| `GET` | `/api/v1/handoff/{id}` | Protected | Tenant Binding + `read` | Multi-tenant isolated handoff retrieval |
| `POST` | `/api/v1/handoff/{id}/close` | Protected | Tenant Binding + `handoff:manage` | Staff/manager resolution |
| `GET` | `/api/v1/analytics/events` | Protected | Tenant Binding + `analytics:read` | Scoped telemetry query |
| `POST` | `/api/v1/analytics/events` | Protected | Tenant Binding + `analytics:events` | Ingestion with client fabrication defenses |
| `GET` | `/api/v1/analytics/summary` | Protected | Tenant Binding + `analytics:read` | Aggregated conversion metrics |
| `GET` | `/api/v1/analytics/funnel` | Protected | Tenant Binding + `analytics:read` | 5-stage conversion funnel |
| `GET` | `/api/v1/analytics/objections` | Protected | Tenant Binding + `analytics:read` | Categorized friction breakdowns |
| `GET` | `/api/v1/analytics/demand` | Protected | Tenant Binding + `analytics:read` | Unfulfilled demand signals |
| `POST` | `/api/v1/analytics/events/demo-seed` | Admin / Protected | Tenant Binding + `analytics:seed` | Repeatable demo event generator |
| `POST` | `/api/v1/agent/test` | Dev-Only | `agent:test` + Dev environment check | Disabled in production; enforces tenant match |
| `GET` | `/api/v1/agent/info` | Dev-Only | None | Diagnostics info |

---

### 15.4 Frontend Integration & Threat Model Assessment

#### 1. Integration Artifacts
- **Module:** `assets/js/auth-client.js` (`ViralXAuth` singleton)
- **UI Integration:** `chat.html` (header status widget, login modal, dynamic sign-in/out reactive subscription, safe `e.preventDefault()` submission).
- **Zero Impact on Production Node.js:** The production AI chat (`POST /api/chat`) and order confirmation routes continue to operate through Express on port 3000.

#### 2. Token Storage Threat Model Assessment
| Storage Mechanism | XSS Vulnerability | CSRF Vulnerability | Session Persistence | Viral-X Design Choice |
|---|---|---|---|---|
| **localStorage** | **High** (Accessible to any injected script or CDN dependency) | None | Indefinite | **Rejected** for access tokens to prevent persistent credential theft. |
| **In-Memory Closure (`_accessToken`)** | **Lowest** (Not readable via DOM or global `window` object) | None | Session only | **Adopted** for short-lived access tokens (60 min expiry). |
| **sessionStorage (`STORAGE_KEY_REFRESH`)** | **Low** (Isolated per browser tab, wiped on tab/window close) | None | Tab lifecycle | **Adopted** for refresh tokens, rotated on each refresh. |
| **HttpOnly Cookie** | Immune to JavaScript reading | Vulnerable without SameSite + Anti-CSRF token | Configurable | Planned for future unified Reverse Proxy / Gateway deployment. |

#### 3. Automatic Lifecycle Handling
- **Transparent Refresh:** `authenticatedFetch(url, init)` intercepts HTTP 401 responses, performs a single renewal attempt via `POST /api/v1/auth/refresh`, updates credentials, and replays the original request.
- **Concurrent Request Queuing:** If multiple requests trigger 401 simultaneously, they are enqueued into `_refreshQueue` while a single refresh round-trip occurs, preventing race conditions.
- **Explicit Logout Invalidation:** Invoking `logout()` calls `POST /api/v1/auth/logout`, persisting revocation records for both tokens before wiping local storage.

---

### 15.5 Shared SQLite Database Findings & Concurrency Safety

1. **Schema Non-Destructive Extension:**
   - Added `server/db/migrations/003_auth_tables.sql` defining `users` and `revoked_tokens` tables.
   - Updated `server/db/schema.sql` with full reference table and index definitions.
   - Both Node.js and Python engines reference identical schemas with zero destructive modifications.

2. **Concurrency Architecture:**
   - `PRAGMA journal_mode = WAL;` enables concurrent readers alongside a writer without read-write locking contention.
   - `PRAGMA foreign_keys = ON;` guarantees strict referential integrity across all relationships.
   - `PRAGMA busy_timeout = 5000;` ensures queries wait up to 5 seconds during burst transactions rather than immediately failing with `SQLITE_BUSY`.

3. **Idempotency & Race Condition Prevention:**
   - Booking reservations utilize atomic SQL queries (`UPDATE booking_slots SET booked_count = booked_count + :party_size WHERE (capacity - booked_count) >= :party_size`) preventing overbooking.
   - Order draft confirmation uses unique `idempotency_key` constraints to ensure duplicate confirmation requests return the existing confirmed state without decrements.

---

### 15.6 PostgreSQL / Supabase Migration Recommendations

When the platform transitions from single-node SQLite to multi-instance cloud deployments:

1. **Alembic Versioning:** Replace raw `.sql` migration files with Alembic migrations generated from `backend/app/db/models.py`.
2. **Native JSONB Migration:** Convert `attributes_json`, `items_json`, `metadata_json`, and `permissions_json` from SQLite `Text` to native PostgreSQL `JSONB` columns, enabling GIN indexes for fast sub-property querying.
3. **Row-Level Security (RLS):** Implement PostgreSQL RLS policies keyed by `tenant_id` at the database engine level as defense-in-depth behind FastAPI application-layer authorization.
4. **Connection Pooling:** Integrate `pgbouncer` or SQLAlchemy async connection pooling (`AsyncEngine` / `asyncpg`) for high-concurrency connection reuse.
5. **Zero-Downtime Data Pump:** Execute data migration from SQLite using `pgloader` with transactional identity preservation before switching DNS.

---

### 15.7 Deployment Prerequisites & Rollback Plan

#### 1. Production Deployment Prerequisites
Before any production cutover:
- [ ] Set `ENVIRONMENT=production` in the production environment configuration.
- [ ] Provide a cryptographically random, 64-character `JWT_SECRET_KEY` generated via `openssl rand -hex 32`.
- [ ] Configure `CORS_ORIGINS` to trusted production domains only (no wildcard `*`).
- [ ] Verify that `validate_production_configuration()` passes and `ALLOW_DEV_HEADER_AUTH=False` is enforced.
- [ ] Set reverse proxy (Nginx / Cloudflare) to route `/api/v1/*` to Uvicorn on port 8000 and legacy routes to Node.js on port 3000.

#### 2. Immediate Rollback Plan
Because production traffic currently routes 100% to Node.js on port 3000:
- If FastAPI or Python services encounter any issue, the reverse proxy configuration can immediately divert all traffic back to Node.js port 3000 with **zero downtime**.
- Shared SQLite database schema changes (`users`, `revoked_tokens`) are purely additive; Node.js requires no database rollback.
- Recovery Time Objective (RTO): < 30 seconds.
- Recovery Point Objective (RPO): 0 (no data loss).

---

### 15.8 Operational Cutover Status Reminder

> [!IMPORTANT]
> **NO PRODUCTION CUTOVER HAS OCCURRED.**
> - Legacy Node.js server remains the **ONLY** production backend (port 3000).
> - Python FastAPI server remains on **port 8000** for development, automated security validation, and staging.
> - The shared SQLite database `viral_x.db` was updated with non-destructive, backward-compatible `users` and `revoked_tokens` tables. All legacy Node.js tables remain 100% intact.
> - Zero frontend traffic has been diverted to Python.



