-- Migration 001: Baseline Schema
-- Multi-Tenant SQLite 3 Schema with Foreign Keys

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
    attributes_json TEXT,
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
    category TEXT NOT NULL,
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
    slot_date TEXT NOT NULL,
    slot_time TEXT NOT NULL,
    service_type TEXT NOT NULL,
    capacity INTEGER NOT NULL DEFAULT 1,
    booked_count INTEGER NOT NULL DEFAULT 0,
    status TEXT DEFAULT 'available',
    FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE
);

-- 6. Customer Chat Sessions
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    customer_name TEXT,
    customer_phone TEXT,
    language TEXT DEFAULT 'en',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE
);

-- 7. Chat Messages
CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    tenant_id TEXT NOT NULL,
    sender TEXT NOT NULL,
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
    status TEXT NOT NULL DEFAULT 'draft',
    draft_type TEXT NOT NULL,
    items_json TEXT NOT NULL,
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

-- 9. Production Audit Logs
CREATE TABLE IF NOT EXISTS audit_logs (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    session_id TEXT,
    action TEXT NOT NULL,
    actor TEXT NOT NULL,
    details_json TEXT,
    ip_address TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_products_tenant ON products(tenant_id);
CREATE INDEX IF NOT EXISTS idx_inventory_tenant ON inventory(tenant_id);
CREATE INDEX IF NOT EXISTS idx_knowledge_tenant ON knowledge_base(tenant_id);
CREATE INDEX IF NOT EXISTS idx_slots_tenant ON booking_slots(tenant_id, slot_date);
CREATE INDEX IF NOT EXISTS idx_drafts_session ON order_drafts(session_id);
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
