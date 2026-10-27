-- Viral-X AI Sales Agent Production Database Schema
-- Multi-Tenant SQLite 3 Schema

PRAGMA foreign_keys = ON;

-- 1. Tenants / Workspaces
CREATE TABLE IF NOT EXISTS tenants (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL, -- 'jewelry', 'restaurant', 'healthcare'
    location TEXT NOT NULL,
    currency TEXT NOT NULL, -- 'QAR', 'EGP', 'USD', etc.
    whatsapp_number TEXT NOT NULL,
    operating_hours TEXT NOT NULL,
    policy_summary TEXT NOT NULL,
    integration_mode TEXT DEFAULT 'demo', -- 'demo', 'live'
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 2. Products / Services Catalog
CREATE TABLE IF NOT EXISTS products (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    sku TEXT NOT NULL,
    name TEXT NOT NULL,
    name_ar TEXT,
    category TEXT NOT NULL,
    base_price REAL NOT NULL,
    currency TEXT NOT NULL,
    description TEXT NOT NULL,
    description_ar TEXT,
    attributes_json TEXT, -- Metal, Carat, Course count, Fasting requirements, etc.
    is_active INTEGER DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE
);

-- 3. Inventory & Live Stock
CREATE TABLE IF NOT EXISTS inventory (
    product_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    stock_count INTEGER NOT NULL DEFAULT 0,
    reserved_count INTEGER NOT NULL DEFAULT 0,
    location TEXT NOT NULL,
    low_stock_threshold INTEGER DEFAULT 1,
    last_verified_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
    FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE
);

-- 4. Business Knowledge Base (FAQs, Policies, Services, Hours)
CREATE TABLE IF NOT EXISTS knowledge_base (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    category TEXT NOT NULL, -- 'policy', 'delivery', 'hours', 'authenticity', 'allergies', 'preparation'
    question TEXT NOT NULL,
    question_ar TEXT,
    answer TEXT NOT NULL,
    answer_ar TEXT,
    tags TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE
);

-- 5. Booking Slots (for Restaurants & Clinics)
CREATE TABLE IF NOT EXISTS booking_slots (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    slot_date TEXT NOT NULL, -- 'YYYY-MM-DD'
    slot_time TEXT NOT NULL, -- 'HH:MM'
    service_type TEXT NOT NULL,
    capacity INTEGER NOT NULL DEFAULT 1,
    booked_count INTEGER NOT NULL DEFAULT 0,
    status TEXT DEFAULT 'available', -- 'available', 'hold', 'booked', 'closed'
    FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE
);

-- 6. Customer Chat Sessions
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    customer_name TEXT,
    customer_phone TEXT,
    language TEXT DEFAULT 'en', -- 'en', 'ar', 'mixed'
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE
);

-- 7. Chat Messages
CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    tenant_id TEXT NOT NULL,
    sender TEXT NOT NULL, -- 'user', 'ai', 'system'
    content TEXT NOT NULL,
    tool_calls_json TEXT,
    grounding_info TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

-- 8. Stateful Order & Booking Drafts
CREATE TABLE IF NOT EXISTS order_drafts (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    tenant_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft', -- 'draft', 'confirmed', 'cancelled', 'expired'
    draft_type TEXT NOT NULL, -- 'product_order', 'table_booking', 'clinical_consultation'
    items_json TEXT NOT NULL, -- Array of items with quantities, validated unit price
    subtotal REAL NOT NULL,
    discount_amount REAL DEFAULT 0,
    tax_amount REAL DEFAULT 0,
    deposit_required REAL DEFAULT 0,
    total_amount REAL NOT NULL,
    currency TEXT NOT NULL,
    customer_notes TEXT,
    idempotency_key TEXT UNIQUE,
    external_reference TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    confirmed_at DATETIME,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
    FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE
);

-- 9. Production Audit Logs (Sensitive actions, explicit confirmations, handoffs)
CREATE TABLE IF NOT EXISTS audit_logs (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    session_id TEXT,
    action TEXT NOT NULL, -- 'DRAFT_CREATED', 'DRAFT_CONFIRMED', 'DRAFT_CANCELLED', 'HANDOFF_TRIGGERED', 'INJECTION_ATTEMPT_BLOCKED'
    actor TEXT NOT NULL, -- 'customer', 'ai_agent', 'system', 'staff'
    details_json TEXT,
    ip_address TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE
);

-- 10. Dedicated Structured Telemetry (bi_events)
CREATE TABLE IF NOT EXISTS bi_events (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    session_id TEXT,
    event_type TEXT NOT NULL,
    category TEXT,
    product_id TEXT,
    sku TEXT,
    draft_id TEXT,
    outcome TEXT,
    metadata_json TEXT,
    is_demo INTEGER DEFAULT 1,
    schema_version TEXT DEFAULT '1.0',
    idempotency_key TEXT UNIQUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE SET NULL,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE SET NULL,
    FOREIGN KEY (draft_id) REFERENCES order_drafts(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_products_tenant ON products(tenant_id);
CREATE INDEX IF NOT EXISTS idx_inventory_tenant ON inventory(tenant_id);
CREATE INDEX IF NOT EXISTS idx_knowledge_tenant ON knowledge_base(tenant_id);
CREATE INDEX IF NOT EXISTS idx_slots_tenant ON booking_slots(tenant_id, slot_date);
CREATE INDEX IF NOT EXISTS idx_drafts_session ON order_drafts(session_id);
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
CREATE INDEX IF NOT EXISTS idx_bi_events_tenant_time ON bi_events(tenant_id, created_at);
CREATE INDEX IF NOT EXISTS idx_bi_events_type ON bi_events(tenant_id, event_type);
CREATE INDEX IF NOT EXISTS idx_bi_events_session ON bi_events(session_id);
CREATE INDEX IF NOT EXISTS idx_bi_events_product ON bi_events(product_id);
CREATE INDEX IF NOT EXISTS idx_bi_events_draft ON bi_events(draft_id);
CREATE INDEX IF NOT EXISTS idx_bi_events_demo ON bi_events(tenant_id, is_demo);

-- 11. Authentication & Users
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    tenant_id TEXT,
    username TEXT UNIQUE NOT NULL,
    hashed_password TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'staff',
    permissions_json TEXT,
    is_active INTEGER DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_tenant ON users(tenant_id);

-- 12. Revoked Tokens (Logout & Replay Protection)
CREATE TABLE IF NOT EXISTS revoked_tokens (
    id TEXT PRIMARY KEY,
    jti TEXT UNIQUE NOT NULL,
    token_type TEXT NOT NULL,
    user_id TEXT,
    reason TEXT,
    revoked_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME
);

CREATE INDEX IF NOT EXISTS idx_revoked_tokens_jti ON revoked_tokens(jti);
CREATE INDEX IF NOT EXISTS idx_revoked_tokens_user ON revoked_tokens(user_id);

