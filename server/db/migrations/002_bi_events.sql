-- Migration 002: Dedicated Structured Telemetry (bi_events)
-- Stores verified business intelligence events with data isolation and auditability.

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

CREATE INDEX IF NOT EXISTS idx_bi_events_tenant_time ON bi_events(tenant_id, created_at);
CREATE INDEX IF NOT EXISTS idx_bi_events_type ON bi_events(tenant_id, event_type);
CREATE INDEX IF NOT EXISTS idx_bi_events_session ON bi_events(session_id);
CREATE INDEX IF NOT EXISTS idx_bi_events_product ON bi_events(product_id);
CREATE INDEX IF NOT EXISTS idx_bi_events_draft ON bi_events(draft_id);
CREATE INDEX IF NOT EXISTS idx_bi_events_demo ON bi_events(tenant_id, is_demo);
