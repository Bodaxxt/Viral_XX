/**
 * Viral-X Production Telemetry & Business Intelligence Event Service
 * Sprint 2 Implementation
 *
 * Provides validated, structured, multi-tenant telemetry ingestion with
 * foreign key integrity, idempotency protection, and sensitive data sanitization.
 */

const { SecurityGuardrails } = require('../ai/guardrails');

const BI_EVENT_TYPES = Object.freeze({
  PRODUCT_SEARCH: 'PRODUCT_SEARCH',
  UNFULFILLED_DEMAND: 'UNFULFILLED_DEMAND',
  OUT_OF_STOCK_DETECTED: 'OUT_OF_STOCK_DETECTED',
  UNANSWERED_QUESTION: 'UNANSWERED_QUESTION',
  DRAFT_CREATED: 'DRAFT_CREATED',
  DRAFT_UPDATED: 'DRAFT_UPDATED',
  DRAFT_CANCELLED: 'DRAFT_CANCELLED',
  DRAFT_CONFIRMED: 'DRAFT_CONFIRMED',
  HUMAN_HANDOFF_REQUESTED: 'HUMAN_HANDOFF_REQUESTED',
  TOOL_EXECUTION_FAILED: 'TOOL_EXECUTION_FAILED',
  LLM_PROVIDER_FAILED: 'LLM_PROVIDER_FAILED',
  SECURITY_GUARDRAIL_TRIGGERED: 'SECURITY_GUARDRAIL_TRIGGERED'
});

const ALLOWED_EVENT_TYPES_SET = new Set(Object.values(BI_EVENT_TYPES));

class TelemetryService {
  constructor(dbManager) {
    this.dbManager = dbManager;
  }

  get db() {
    return this.dbManager.db;
  }

  /**
   * Records a validated BI event into `bi_events`.
   */
  recordEvent({
    tenantId,
    eventType,
    sessionId = null,
    category = null,
    productId = null,
    sku = null,
    draftId = null,
    outcome = 'success',
    metadata = {},
    isDemo = null,
    idempotencyKey = null,
    schemaVersion = '1.0'
  }) {
    // 1. Validate tenant existence
    if (!tenantId || typeof tenantId !== 'string') {
      throw new Error('Telemetry Error: tenantId is required and must be a string.');
    }
    const tenant = this.dbManager.getTenant(tenantId);
    if (!tenant) {
      throw new Error(`Telemetry Error: Tenant '${tenantId}' does not exist.`);
    }

    // 2. Validate event type against strict whitelist
    if (!eventType || !ALLOWED_EVENT_TYPES_SET.has(eventType)) {
      throw new Error(`Telemetry Error: Invalid event_type '${eventType}'. Must be one of: ${Array.from(ALLOWED_EVENT_TYPES_SET).join(', ')}`);
    }

    // 3. Demo vs Production classification
    // If not explicitly provided, derive from tenant's integration_mode
    const demoFlag = isDemo !== null ? (isDemo ? 1 : 0) : (tenant.integration_mode === 'demo' ? 1 : 0);

    // 4. Idempotency check
    if (idempotencyKey) {
      const existing = this.db.prepare('SELECT * FROM bi_events WHERE idempotency_key = ?').get(idempotencyKey);
      if (existing) {
        return {
          success: true,
          duplicate: true,
          event: this._formatEvent(existing)
        };
      }
    }

    // 5. Foreign Key / Relationship Validation
    if (sessionId) {
      // Ensure session exists
      this.dbManager.getOrCreateSession(sessionId, tenantId);
    }

    if (draftId) {
      const draft = this.dbManager.getDraft(draftId);
      if (draft && draft.tenant_id !== tenantId) {
        throw new Error('Telemetry Error: draftId belongs to a different tenant.');
      }
    }

    // 6. Sanitize metadata (PCI-DSS & Sensitive Data Redaction)
    const sanitizedMetadata = this._sanitizeMetadata(metadata);

    // 7. Insert event
    const eventId = `EVT-${Date.now()}-${Math.random().toString(36).substr(2, 6)}`;
    
    this.db.prepare(`
      INSERT INTO bi_events (
        id, tenant_id, session_id, event_type, category, product_id, sku,
        draft_id, outcome, metadata_json, is_demo, schema_version, idempotency_key
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `).run(
      eventId,
      tenantId,
      sessionId,
      eventType,
      category,
      productId,
      sku,
      draftId,
      outcome,
      JSON.stringify(sanitizedMetadata),
      demoFlag,
      schemaVersion,
      idempotencyKey || null
    );

    const created = this.db.prepare('SELECT * FROM bi_events WHERE id = ?').get(eventId);
    return {
      success: true,
      duplicate: false,
      event: this._formatEvent(created)
    };
  }

  /**
   * Queries events for a given tenant with isolation and filters.
   */
  getEvents({
    tenantId,
    eventType = null,
    sessionId = null,
    isDemo = null,
    limit = 50,
    offset = 0
  }) {
    if (!tenantId) throw new Error('tenantId is required for event queries.');

    let sql = 'SELECT * FROM bi_events WHERE tenant_id = ?';
    const params = [tenantId];

    if (eventType) {
      sql += ' AND event_type = ?';
      params.push(eventType);
    }
    if (sessionId) {
      sql += ' AND session_id = ?';
      params.push(sessionId);
    }
    if (isDemo !== null) {
      sql += ' AND is_demo = ?';
      params.push(isDemo ? 1 : 0);
    }

    sql += ' ORDER BY created_at DESC LIMIT ? OFFSET ?';
    params.push(Number(limit) || 50, Number(offset) || 0);

    const rows = this.db.prepare(sql).all(...params);
    return rows.map(r => this._formatEvent(r));
  }

  /**
   * Aggregates event telemetry summary for a tenant.
   */
  getTelemetrySummary(tenantId, { isDemo = null, days = 30 } = {}) {
    if (!tenantId) throw new Error('tenantId is required.');

    let sql = `
      SELECT event_type, outcome, COUNT(*) as count
      FROM bi_events
      WHERE tenant_id = ?
        AND created_at >= datetime('now', '-' || ? || ' days')
    `;
    const params = [tenantId, Number(days) || 30];

    if (isDemo !== null) {
      sql += ' AND is_demo = ?';
      params.push(isDemo ? 1 : 0);
    }

    sql += ' GROUP BY event_type, outcome';
    const rows = this.db.prepare(sql).all(...params);

    const summary = {
      tenant_id: tenantId,
      timeframe_days: days,
      total_events: 0,
      by_event_type: {},
      funnel: {
        searches: 0,
        unfulfilled: 0,
        out_of_stock: 0,
        drafts_created: 0,
        drafts_confirmed: 0,
        drafts_cancelled: 0,
        handoffs: 0
      }
    };

    for (const r of rows) {
      summary.total_events += r.count;
      summary.by_event_type[r.event_type] = (summary.by_event_type[r.event_type] || 0) + r.count;

      if (r.event_type === BI_EVENT_TYPES.PRODUCT_SEARCH) summary.funnel.searches += r.count;
      if (r.event_type === BI_EVENT_TYPES.UNFULFILLED_DEMAND) summary.funnel.unfulfilled += r.count;
      if (r.event_type === BI_EVENT_TYPES.OUT_OF_STOCK_DETECTED) summary.funnel.out_of_stock += r.count;
      if (r.event_type === BI_EVENT_TYPES.DRAFT_CREATED) summary.funnel.drafts_created += r.count;
      if (r.event_type === BI_EVENT_TYPES.DRAFT_CONFIRMED) summary.funnel.drafts_confirmed += r.count;
      if (r.event_type === BI_EVENT_TYPES.DRAFT_CANCELLED) summary.funnel.drafts_cancelled += r.count;
      if (r.event_type === BI_EVENT_TYPES.HUMAN_HANDOFF_REQUESTED) summary.funnel.handoffs += r.count;
    }

    return summary;
  }

  /**
   * Calculates 5-stage conversion funnel metrics for a tenant.
   */
  getFunnelMetrics(tenantId, { isDemo = null, days = 30 } = {}) {
    if (!tenantId) throw new Error('tenantId is required.');

    let demoFilter = '';
    const demoParam = [];
    if (isDemo !== null) {
      demoFilter = ' AND is_demo = ?';
      demoParam.push(isDemo ? 1 : 0);
    }

    // 1. Inbound sessions
    const sessionsRow = this.db.prepare(`
      SELECT COUNT(*) as count FROM sessions
      WHERE tenant_id = ? AND created_at >= datetime('now', '-' || ? || ' days')
    `).get(tenantId, Number(days) || 30);
    const totalSessions = sessionsRow ? sessionsRow.count : 0;

    // 2. Event type counts
    const countsSql = `
      SELECT event_type, outcome, COUNT(*) as count
      FROM bi_events
      WHERE tenant_id = ? AND created_at >= datetime('now', '-' || ? || ' days') ${demoFilter}
      GROUP BY event_type, outcome
    `;
    const rows = this.db.prepare(countsSql).all(tenantId, Number(days) || 30, ...demoParam);

    let searches = 0;
    let successfulSearches = 0;
    let draftsCreated = 0;
    let draftsConfirmed = 0;

    for (const r of rows) {
      if (r.event_type === BI_EVENT_TYPES.PRODUCT_SEARCH) {
        searches += r.count;
        if (r.outcome === 'success') successfulSearches += r.count;
      }
      if (r.event_type === BI_EVENT_TYPES.DRAFT_CREATED) {
        draftsCreated += r.count;
      }
      if (r.event_type === BI_EVENT_TYPES.DRAFT_CONFIRMED) {
        draftsConfirmed += r.count;
      }
    }

    // 5 stages
    const baseInquiries = Math.max(totalSessions, searches, 1);
    const stages = [
      {
        stage: 'Inbound Customer Inquiries',
        count: totalSessions,
        conversionRate: '100.0%'
      },
      {
        stage: 'Catalog & Inventory Engaged',
        count: searches,
        conversionRate: totalSessions > 0 ? `${((searches / totalSessions) * 100).toFixed(1)}%` : '0.0%'
      },
      {
        stage: 'Grounded Product Recommendation',
        count: successfulSearches,
        conversionRate: searches > 0 ? `${((successfulSearches / searches) * 100).toFixed(1)}%` : '0.0%'
      },
      {
        stage: 'Order or Booking Drafted',
        count: draftsCreated,
        conversionRate: searches > 0 ? `${((draftsCreated / searches) * 100).toFixed(1)}%` : '0.0%'
      },
      {
        stage: 'Explicit Customer Confirmation',
        count: draftsConfirmed,
        conversionRate: draftsCreated > 0 ? `${((draftsConfirmed / draftsCreated) * 100).toFixed(1)}%` : '0.0%'
      }
    ];

    return {
      tenant_id: tenantId,
      timeframe_days: Number(days) || 30,
      overallConversionRate: baseInquiries > 0 ? `${((draftsConfirmed / baseInquiries) * 100).toFixed(1)}%` : '0.0%',
      stages
    };
  }

  /**
   * Retrieves categorized purchase objections and friction points.
   */
  getObjectionBreakdown(tenantId, { isDemo = null, days = 30 } = {}) {
    if (!tenantId) throw new Error('tenantId is required.');

    let sql = `
      SELECT event_type, category, outcome, COUNT(*) as count
      FROM bi_events
      WHERE tenant_id = ?
        AND event_type IN (?, ?, ?, ?)
        AND created_at >= datetime('now', '-' || ? || ' days')
    `;
    const params = [
      tenantId,
      BI_EVENT_TYPES.UNFULFILLED_DEMAND,
      BI_EVENT_TYPES.OUT_OF_STOCK_DETECTED,
      BI_EVENT_TYPES.UNANSWERED_QUESTION,
      BI_EVENT_TYPES.DRAFT_CANCELLED,
      Number(days) || 30
    ];

    if (isDemo !== null) {
      sql += ' AND is_demo = ?';
      params.push(isDemo ? 1 : 0);
    }

    sql += ' GROUP BY event_type, category, outcome ORDER BY count DESC';
    const rows = this.db.prepare(sql).all(...params);

    const categories = {
      out_of_stock: 0,
      unfulfilled_searches: 0,
      unanswered_questions: 0,
      cancelled_drafts: 0
    };

    for (const r of rows) {
      if (r.event_type === BI_EVENT_TYPES.OUT_OF_STOCK_DETECTED) categories.out_of_stock += r.count;
      if (r.event_type === BI_EVENT_TYPES.UNFULFILLED_DEMAND) categories.unfulfilled_searches += r.count;
      if (r.event_type === BI_EVENT_TYPES.UNANSWERED_QUESTION) categories.unanswered_questions += r.count;
      if (r.event_type === BI_EVENT_TYPES.DRAFT_CANCELLED) categories.cancelled_drafts += r.count;
    }

    return {
      tenant_id: tenantId,
      timeframe_days: Number(days) || 30,
      total_objections: Object.values(categories).reduce((a, b) => a + b, 0),
      summary: categories,
      breakdown: rows
    };
  }

  /**
   * Extracts top unfulfilled product and inventory demand signals.
   */
  getUnfulfilledDemandSignals(tenantId, { isDemo = null, days = 30, limit = 10 } = {}) {
    if (!tenantId) throw new Error('tenantId is required.');

    let sql = `
      SELECT event_type, product_id, sku, category, metadata_json, created_at
      FROM bi_events
      WHERE tenant_id = ?
        AND event_type IN (?, ?)
        AND created_at >= datetime('now', '-' || ? || ' days')
    `;
    const params = [
      tenantId,
      BI_EVENT_TYPES.UNFULFILLED_DEMAND,
      BI_EVENT_TYPES.OUT_OF_STOCK_DETECTED,
      Number(days) || 30
    ];

    if (isDemo !== null) {
      sql += ' AND is_demo = ?';
      params.push(isDemo ? 1 : 0);
    }

    sql += ' ORDER BY created_at DESC LIMIT ?';
    params.push(Number(limit) || 10);

    const rows = this.db.prepare(sql).all(...params);
    return rows.map(r => this._formatEvent(r));
  }

  _sanitizeMetadata(metadata) {
    if (!metadata || typeof metadata !== 'object') return {};

    const clean = {};
    for (const [key, val] of Object.entries(metadata)) {
      // Omit dangerous fields
      if (['password', 'token', 'api_key', 'secret', 'authorization'].includes(key.toLowerCase())) {
        continue;
      }
      if (typeof val === 'string') {
        // Redact any credit cards or sensitive strings
        clean[key] = SecurityGuardrails.redactSensitive(val).substring(0, 500);
      } else if (typeof val === 'number' || typeof val === 'boolean' || val === null) {
        clean[key] = val;
      } else if (Array.isArray(val)) {
        clean[key] = val.slice(0, 10);
      } else if (typeof val === 'object') {
        clean[key] = this._sanitizeMetadata(val);
      }
    }
    return clean;
  }

  _formatEvent(row) {
    if (!row) return null;
    let metadata = {};
    try {
      metadata = JSON.parse(row.metadata_json || '{}');
    } catch {
      metadata = {};
    }
    return {
      id: row.id,
      tenantId: row.tenant_id,
      sessionId: row.session_id,
      eventType: row.event_type,
      category: row.category,
      productId: row.product_id,
      sku: row.sku,
      draftId: row.draft_id,
      outcome: row.outcome,
      metadata,
      isDemo: Boolean(row.is_demo),
      schemaVersion: row.schema_version,
      idempotencyKey: row.idempotency_key,
      createdAt: row.created_at
    };
  }
}

module.exports = {
  TelemetryService,
  BI_EVENT_TYPES
};
