# Viral-X AI Sales Agent — Production Intelligence System

A production-grade, multi-tenant AI Sales Agent built with Node.js + SQLite. Supports real LLM providers (Google Gemini, Anthropic Claude, OpenAI) with proper function-calling tool use, deterministic server-side pricing, persistent draft orders, and safe human handoff.

---

## Quick Start

```bash
# 1. Install dependencies
npm install

# 2. Copy environment config
cp .env.example .env

# 3. (Optional) Add a real LLM key in .env
#    GEMINI_API_KEY=...  or  ANTHROPIC_API_KEY=...  or  OPENAI_API_KEY=...

# 4. Start the server
npm run dev
# → http://localhost:3000

# 5. Open the AI chat demo
# → http://localhost:3000/chat.html

# 6. Run the test suite
npm test
```

---

## Project Structure

```
viral_X/
├── backend/                    ← Python + FastAPI backend foundation (Sprint 2.5)
│   ├── app/                    ← FastAPI, Pydantic schemas, SQLAlchemy models
│   ├── tests/                  ← Automated Pytest suite (29 tests)
│   ├── requirements.txt        ← Pinned Python dependencies
│   └── README.md               ← Python backend documentation
├── server/
│   ├── ai/
│   │   ├── aiAgent.js          ← LLM orchestrator (Gemini / Claude / OpenAI / Local)
│   │   ├── promptTemplates.js  ← System prompt builder per tenant
│   │   └── guardrails.js       ← Prompt injection defense
│   ├── db/
│   │   ├── database.js         ← SQLite data access layer
│   │   ├── schema.sql          ← Full database schema (10 tables)
│   │   └── seedData.js         ← Demo data for 3 business tenants
│   ├── tools/
│   │   └── toolRegistry.js     ← 10 typed server-side tools
│   ├── adapters/
│   │   └── externalIntegrations.js ← Shopify / WooCommerce / EHR adapters
│   ├── routes/
│   │   ├── chatRoutes.js       ← POST /api/chat, GET /api/chat/history/:id
│   │   ├── draftRoutes.js      ← Draft confirm / cancel endpoints
│   │   ├── tenantRoutes.js     ← Tenant & catalog API
│   │   ├── analyticsRoutes.js  ← BI telemetry & funnel endpoints
│   │   └── handoffRoutes.js    ← WhatsApp escalation
│   ├── middleware/
│   │   └── security.js         ← Rate limiter, static security & error handler
│   ├── tests/
│   │   ├── salesAgent.test.js  ← 18 automated agent tests
│   │   └── sprint2SecurityAndBI.test.js ← 36 automated security & BI tests
│   ├── app.js
│   └── server.js
├── assets/
│   ├── css/
│   │   ├── main.css            ← Viral-X design system
│   │   └── chat.css            ← Chat interface styles
│   └── js/
│       ├── chat.js             ← Production chat client (new)
│       ├── ai-sales-demo.js    ← Legacy embedded demo client
│       └── ...
├── chat.html                   ← Full-featured AI chat page
├── index.html                  ← Studio website
├── viral_x.db                  ← SQLite production database
├── .env.example                ← Environment template
└── README.md
```

---

## LLM Provider Configuration

The agent auto-detects which provider to use. Priority: **Gemini > Anthropic > OpenAI > Local**.

### Google Gemini (Recommended)
```env
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-2.0-flash
```
Get a key: https://aistudio.google.com/

### Anthropic Claude
```env
ANTHROPIC_API_KEY=your_key_here
ANTHROPIC_MODEL=claude-sonnet-4-5
```
Get a key: https://console.anthropic.com/

### OpenAI GPT
```env
OPENAI_API_KEY=your_key_here
OPENAI_MODEL=gpt-4o-mini
```
Get a key: https://platform.openai.com/

### No Key → Demo Mode
Without any API key, the agent uses the high-quality local deterministic orchestrator. All tools still execute against the real database — the difference is language understanding quality.

---

## Available API Endpoints

| Method | Route | Description |
|--------|-------|-------------|
| `POST` | `/api/chat` | Send a message, receive AI reply with tool data |
| `GET` | `/api/chat/history/:sessionId` | Retrieve conversation history |
| `GET` | `/api/drafts/:draftId` | Get an order draft |
| `POST` | `/api/drafts/confirm` | Explicitly confirm a draft (idempotent) |
| `POST` | `/api/drafts/cancel` | Cancel a draft |
| `GET` | `/api/tenants` | List all business tenants |
| `GET` | `/api/tenants/:tenantId` | Get tenant info |
| `GET` | `/api/tenants/:tenantId/catalog` | Get full catalog |
| `GET` | `/api/integrations` | Integration adapter statuses |
| `POST` | `/api/handoff/whatsapp` | Generate WhatsApp handoff URL |
| `GET` | `/api/health` | Server health check |

### Chat Request Example

```bash
curl -X POST http://localhost:3000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "tenantId": "al-noor-jewelry",
    "sessionId": "SES-DEMO-001",
    "message": "ما هو سعر طوق الزمرد وهل متوفر في الدوحة؟"
  }'
```

---

## Business Workspaces (Demo Data)

### 💎 Al Noor High Jewelry (`al-noor-jewelry`)
- **Location:** Place Vendôme, Doha, Qatar
- **Currency:** QAR
- **Products:** Diamond rings, emerald collars, gold pieces (J-101 to J-105)
- **WhatsApp:** +974 4499 1200
- **Pricing Rules:** 0% VAT, insured courier 250 QAR under 20,000 QAR

### 🍽️ The Saffron Table (`saffron-table`)
- **Location:** Zamalek, Cairo, Egypt
- **Currency:** EGP
- **Menus:** Chef tasting, à la carte, vegetarian (R-201 to R-205)
- **WhatsApp:** +20 2 3735 9200
- **Pricing Rules:** 14% VAT + 500 EGP deposit per guest

### 🩺 Vitalis Clinical Health (`vitalis-health`)
- **Location:** New Cairo Medical Park, Egypt
- **Currency:** EGP
- **Services:** Executive longevity screening, cardiac panel, oncology screening (H-301 to H-305)
- **WhatsApp:** +20 2 2617 0300
- **Pricing Rules:** 14% clinical administration VAT

---

## Connecting a Real Business

### 1. Add a New Tenant

Insert into `tenants` table in `viral_x.db`:

```sql
INSERT INTO tenants (id, name, category, location, currency, whatsapp_number, operating_hours, policy_summary, integration_mode)
VALUES ('my-business', 'My Business Name', 'jewelry', 'Dubai, UAE', 'AED', '+971501234567', 'Mon-Sat 9am-9pm', 'Premium boutique policy...', 'demo');
```

Then seed products, inventory, knowledge base, and booking slots similarly.

### 2. Connect Shopify

```env
SHOPIFY_SHOP_DOMAIN=your-shop.myshopify.com
SHOPIFY_ACCESS_TOKEN=shpat_...
```

### 3. Connect WooCommerce

```env
WOOCOMMERCE_URL=https://your-shop.com
WOOCOMMERCE_KEY=ck_...
WOOCOMMERCE_SECRET=cs_...
```

### 4. Connect WhatsApp Business API

```env
WHATSAPP_CLOUD_TOKEN=your_cloud_token
WHATSAPP_PHONE_NUMBER_ID=your_phone_number_id
```

Without credentials, the system generates `wa.me/` links (no API call is falsely claimed).

---

## Agent Tools

All tools execute on the server — the LLM only decides which tool to call, not how to execute it.

| Tool | Description |
|------|-------------|
| `search_products` | Full-text search across tenant catalog |
| `get_product_details` | Rich product info including attributes |
| `check_inventory` | Real stock count from DB or connected ERP |
| `calculate_price` | Deterministic: subtotal, VAT, discount, deposit |
| `search_business_knowledge` | FAQs, policies, hours, allergen info |
| `check_booking_availability` | Available slots from DB or booking API |
| `create_order_draft` | Persistent draft with validated pricing |
| `update_order_draft` | Modify quantities/notes, re-validates stock |
| `get_order_draft` | Retrieve current draft status |
| `request_human_handoff` | Build WhatsApp escalation with full context |

---

## Security Features

- ✅ Prompt injection detection (English + Arabic patterns)
- ✅ Tenant isolation — queries strictly scoped to `tenant_id`
- ✅ Server-side payload validation on all routes
- ✅ Rate limiting (120 req/min per IP)
- ✅ API keys never exposed to client
- ✅ Idempotency protection on draft confirmation
- ✅ Stock validation before confirmation
- ✅ Card number redaction from audit logs
- ✅ Cross-tenant draft modification blocked
- ✅ Max tool execution rounds (6) to prevent infinite loops
- ✅ Request timeout (60s on client)

---

## What is Fully Functional

| Feature | Status |
|---------|--------|
| Multi-tenant SQLite database | ✅ Production |
| 10 server-side tools | ✅ Production |
| Deterministic pricing engine | ✅ Production |
| Draft order lifecycle (create/confirm/cancel) | ✅ Production |
| Idempotency on confirmation | ✅ Production |
| Audit logging | ✅ Production |
| Prompt injection defense | ✅ Production |
| Multi-tenant isolation | ✅ Production |
| WhatsApp handoff URL generation | ✅ Production |
| Human handoff with context summary | ✅ Production |
| Local deterministic orchestrator | ✅ Production |
| Arabic / Egyptian Arabic / mixed language | ✅ Production |
| Gemini function-calling integration | ✅ Production (key required) |
| Anthropic tool-use integration | ✅ Production (key required) |
| OpenAI tool-calls integration | ✅ Production (key required) |
| Dedicated chat UI (`chat.html`) | ✅ Production |
| Automated test suite (18 tests) | ✅ All passing |

## What Requires Client Credentials

| Feature | Requirement |
|---------|-------------|
| Real LLM intelligence | Gemini / Anthropic / OpenAI API key |
| Shopify inventory sync | Shopify domain + access token |
| WooCommerce sync | WooCommerce URL + key + secret |
| Live restaurant booking | SevenRooms / Resy API key |
| Clinical EHR scheduling | HL7/FHIR endpoint + token |
| WhatsApp API delivery (not just link) | WhatsApp Cloud API token |

---

## Running Tests

### Node.js Test Suite (All 54 tests passing)
```bash
npm test
# Or run with Node native test runner:
node --test server/tests/*.test.js
```
Covers: Arabic/English/mixed language, multi-turn corrections, deterministic pricing, out-of-stock handling, draft lifecycle, idempotency, prompt injection, tenant isolation, handoff URL, integration fallback, static file traversal security, and BI telemetry aggregation.

### Python Backend Test Suite (All 29 tests passing)
```bash
python -m pytest backend/tests -v
```
Covers: FastAPI startup, health/readiness probes, SQLite connectivity & degradation, tenant isolation, proof-of-concept catalog retrieval, request size limits, path traversal defenses, and configuration secret masking.

See [docs/python-migration-plan.md](file:///c:/Users/d/Desktop/viral_X/docs/python-migration-plan.md) and [backend/README.md](file:///c:/Users/d/Desktop/viral_X/backend/README.md) for full architectural details.

---

## Deployment

The server serves static files from the project root. For production:

1. Set `NODE_ENV=production`
2. Use a process manager (PM2): `pm2 start server/server.js`
3. Reverse-proxy with Nginx or Caddy
4. Set `DATABASE_PATH` to a persistent volume outside the app directory
5. Never commit `.env` to version control
