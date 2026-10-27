/**
 * Viral-X Database Layer
 * Uses Node's built-in native SQLite engine (DatabaseSync).
 * Provides atomic transactions, prepared statements, and persistent storage.
 */

const fs = require('fs');
const path = require('path');
const { DatabaseSync } = require('node:sqlite');
const seedData = require('./seedData');
const { TelemetryService } = require('../analytics/telemetryService');

const DB_PATH = process.env.DATABASE_PATH || (process.env.VERCEL ? path.join('/tmp', 'viral_x.db') : path.join(__dirname, '../../viral_x.db'));

class DatabaseManager {
  constructor(dbPath = DB_PATH) {
    this.dbPath = dbPath;
    this.db = new DatabaseSync(this.dbPath);
    this.init();
    this.telemetry = new TelemetryService(this);
  }

  init() {
    // 1. Concurrency and safety pragmas
    this.db.exec('PRAGMA foreign_keys = ON;');
    this.db.exec('PRAGMA journal_mode = WAL;');
    this.db.exec('PRAGMA busy_timeout = 5000;');

    // 2. Versioned migrations
    this.runMigrations();

    // 3. Seed demo data if database is empty
    this.seedIfEmpty();
  }

  transaction(fn) {
    if (this._inTransaction) {
      return fn();
    }
    this._inTransaction = true;
    this.db.exec('BEGIN TRANSACTION;');
    try {
      const result = fn();
      this.db.exec('COMMIT;');
      this._inTransaction = false;
      return result;
    } catch (err) {
      try {
        this.db.exec('ROLLBACK;');
      } catch (rollbackErr) {
        // Suppress rollback errors if already rolled back
      }
      this._inTransaction = false;
      throw err;
    }
  }

  runMigrations() {
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS schema_migrations (
        version INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        applied_at DATETIME DEFAULT CURRENT_TIMESTAMP
      );
    `);

    const migrationsDir = path.join(__dirname, 'migrations');
    if (fs.existsSync(migrationsDir)) {
      const files = fs.readdirSync(migrationsDir).filter(f => f.endsWith('.sql')).sort();
      for (const file of files) {
        const version = parseInt(file.split('_')[0], 10);
        const row = this.db.prepare('SELECT version FROM schema_migrations WHERE version = ?').get(version);
        if (!row) {
          const sql = fs.readFileSync(path.join(migrationsDir, file), 'utf-8');
          this.transaction(() => {
            this.db.exec(sql);
            this.db.prepare('INSERT INTO schema_migrations (version, name) VALUES (?, ?)').run(version, file);
          });
        }
      }
    } else {
      // Fallback to schema.sql if migrations directory is missing
      const schemaSql = fs.readFileSync(path.join(__dirname, 'schema.sql'), 'utf-8');
      this.db.exec(schemaSql);
    }
  }

  seedIfEmpty() {
    const tenantCount = this.db.prepare('SELECT COUNT(*) as count FROM tenants').get();
    if (tenantCount.count === 0) {
      this.seedDemoData();
    }
  }

  seedDemoData() {
    return this.transaction(() => {
      // Seed tenants (idempotent INSERT OR REPLACE)
      const insertTenant = this.db.prepare(`
        INSERT OR REPLACE INTO tenants (id, name, category, location, currency, whatsapp_number, operating_hours, policy_summary, integration_mode)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
      `);
      for (const t of seedData.tenants) {
        insertTenant.run(t.id, t.name, t.category, t.location, t.currency, t.whatsapp_number, t.operating_hours, t.policy_summary, t.integration_mode || 'demo');
      }

      // Seed products (idempotent INSERT OR REPLACE)
      const insertProduct = this.db.prepare(`
        INSERT OR REPLACE INTO products (id, tenant_id, sku, name, name_ar, category, base_price, currency, description, description_ar, attributes_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
      `);
      for (const p of seedData.products) {
        insertProduct.run(
          p.id, p.tenant_id, p.sku, p.name, p.name_ar, p.category, p.base_price, p.currency,
          p.description, p.description_ar, JSON.stringify(p.attributes || {})
        );
      }

      // Seed inventory (idempotent INSERT OR REPLACE)
      const insertInventory = this.db.prepare(`
        INSERT OR REPLACE INTO inventory (product_id, tenant_id, stock_count, reserved_count, location)
        VALUES (?, ?, ?, ?, ?)
      `);
      for (const inv of seedData.inventory) {
        insertInventory.run(inv.product_id, inv.tenant_id, inv.stock_count, inv.reserved_count, inv.location);
      }

      // Seed knowledge base (idempotent INSERT OR REPLACE)
      const insertKB = this.db.prepare(`
        INSERT OR REPLACE INTO knowledge_base (id, tenant_id, category, question, question_ar, answer, answer_ar, tags)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
      `);
      for (const kb of seedData.knowledge_base) {
        insertKB.run(kb.id, kb.tenant_id, kb.category, kb.question, kb.question_ar, kb.answer, kb.answer_ar, kb.tags);
      }

      // Seed booking slots (idempotent INSERT OR REPLACE)
      const insertSlot = this.db.prepare(`
        INSERT OR REPLACE INTO booking_slots (id, tenant_id, slot_date, slot_time, service_type, capacity, booked_count, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
      `);
      for (const s of seedData.booking_slots) {
        insertSlot.run(s.id, s.tenant_id, s.slot_date, s.slot_time, s.service_type, s.capacity, s.booked_count, s.status);
      }

      return true;
    });
  }

  // --- Helper Query Methods ---

  getTenant(tenantId) {
    return this.db.prepare('SELECT * FROM tenants WHERE id = ?').get(tenantId);
  }

  listTenants() {
    return this.db.prepare('SELECT id, name, category, location, currency, operating_hours, integration_mode FROM tenants').all();
  }

  searchProducts(tenantId, query, category, maxBudget) {
    let sql = `
      SELECT p.*, i.stock_count, i.reserved_count, i.location as inventory_location
      FROM products p
      LEFT JOIN inventory i ON p.id = i.product_id
      WHERE p.tenant_id = ? AND p.is_active = 1
    `;
    const params = [tenantId];

    if (category && category.trim()) {
      sql += ` AND p.category LIKE ?`;
      params.push(`%${category.trim()}%`);
    }

    if (maxBudget && Number(maxBudget) > 0) {
      sql += ` AND p.base_price <= ?`;
      params.push(Number(maxBudget));
    }

    sql += ` ORDER BY p.base_price ASC`;
    const allProducts = this.db.prepare(sql).all(...params);

    if (!query || !query.trim()) {
      return allProducts.slice(0, 20);
    }

    const qClean = query.trim().toLowerCase();
    const scored = allProducts.map(p => {
      let score = 0;
      const skuLower = (p.sku || '').toLowerCase();
      const nameLower = (p.name || '').toLowerCase();
      const nameAr = (p.name_ar || '').toLowerCase();
      const descLower = (p.description || '').toLowerCase();
      const descAr = (p.description_ar || '').toLowerCase();

      // Direct match
      if (skuLower && qClean.includes(skuLower)) score += 50;
      if (p.id && qClean.includes(p.id.toLowerCase())) score += 50;
      if (nameLower && qClean.includes(nameLower)) score += 30;
      if (nameAr && qClean.includes(nameAr)) score += 30;

      // Token match
      const stopWords = [
        'want', 'purchase', 'buy', 'check', 'the', 'and', 'for', 'with', 'what', 'price',
        'guests', 'guest', 'table', 'book', 'booking', 'tomorrow', 'today', 'dinner', 'night', 'menu',
        'سعر', 'عايز', 'شراء', 'هل', 'كوليه', 'بكرة', 'ترابيزة', 'شخصين', 'أفراد', 'حجز', 'غدا', 'عشاء'
      ];
      const tokens = qClean.split(/[\s,()\-—/]+/).filter(t => t.length >= 2 && !stopWords.includes(t));
      for (const tok of tokens) {
        if (skuLower.includes(tok)) score += 25;
        if (nameLower.includes(tok)) score += 20;
        if (nameAr.includes(tok)) score += 20;
        if ((p.category || '').toLowerCase().includes(tok)) score += 15;
        if (descLower.includes(tok)) score += 5;
        if (descAr.includes(tok)) score += 5;
      }

      return { product: p, score };
    });

    const matches = scored.filter(s => s.score > 0).sort((a, b) => b.score - a.score).map(s => s.product);
    return matches.length > 0 ? matches.slice(0, 20) : [];
  }

  getProductById(tenantId, productId) {
    const product = this.db.prepare(`
      SELECT p.*, i.stock_count, i.reserved_count, i.location as inventory_location
      FROM products p
      LEFT JOIN inventory i ON p.id = i.product_id
      WHERE p.tenant_id = ? AND (p.id = ? OR p.sku = ?)
    `).get(tenantId, productId, productId);

    if (product && product.attributes_json) {
      try {
        product.attributes = JSON.parse(product.attributes_json);
      } catch (e) {
        product.attributes = {};
      }
    }
    return product;
  }

  getInventory(tenantId, productId) {
    return this.db.prepare(`
      SELECT i.*, p.name, p.sku, p.base_price, p.currency
      FROM inventory i
      JOIN products p ON i.product_id = p.id
      WHERE i.tenant_id = ? AND (i.product_id = ? OR p.sku = ?)
    `).get(tenantId, productId, productId);
  }

  searchKnowledge(tenantId, query, category) {
    let sql = `SELECT * FROM knowledge_base WHERE tenant_id = ?`;
    const params = [tenantId];

    if (query && query.trim()) {
      const term = `%${query.trim()}%`;
      sql += ` AND (question LIKE ? OR question_ar LIKE ? OR answer LIKE ? OR answer_ar LIKE ? OR tags LIKE ?)`;
      params.push(term, term, term, term, term);
    }

    if (category && category.trim()) {
      sql += ` AND category = ?`;
      params.push(category.trim());
    }

    sql += ` LIMIT 5`;
    return this.db.prepare(sql).all(...params);
  }

  getBookingSlots(tenantId, date, serviceType) {
    let sql = `SELECT * FROM booking_slots WHERE tenant_id = ?`;
    const params = [tenantId];

    if (date) {
      sql += ` AND slot_date = ?`;
      params.push(date);
    }

    if (serviceType) {
      sql += ` AND service_type LIKE ?`;
      params.push(`%${serviceType}%`);
    }

    sql += ` ORDER BY slot_date ASC, slot_time ASC`;
    return this.db.prepare(sql).all(...params);
  }

  // --- Session & Messages ---

  getOrCreateSession(sessionId, tenantId, customerName = null, language = 'en') {
    let session = this.db.prepare('SELECT * FROM sessions WHERE id = ?').get(sessionId);
    if (!session) {
      this.db.prepare(`
        INSERT INTO sessions (id, tenant_id, customer_name, language)
        VALUES (?, ?, ?, ?)
      `).run(sessionId, tenantId, customerName, language);
      session = this.db.prepare('SELECT * FROM sessions WHERE id = ?').get(sessionId);
    }
    return session;
  }

  saveMessage(id, sessionId, tenantId, sender, content, toolCalls = null, groundingInfo = null) {
    this.db.prepare(`
      INSERT INTO messages (id, session_id, tenant_id, sender, content, tool_calls_json, grounding_info)
      VALUES (?, ?, ?, ?, ?, ?, ?)
    `).run(
      id,
      sessionId,
      tenantId,
      sender,
      content,
      toolCalls ? JSON.stringify(toolCalls) : null,
      groundingInfo
    );
  }

  getSessionMessages(sessionId, limit = 20) {
    return this.db.prepare(`
      SELECT * FROM messages
      WHERE session_id = ?
      ORDER BY created_at ASC
      LIMIT ?
    `).all(sessionId, limit);
  }

  // --- Order & Booking Drafts ---

  saveDraft(draft) {
    const existing = this.db.prepare('SELECT id FROM order_drafts WHERE id = ?').get(draft.id);
    if (existing) {
      this.db.prepare(`
        UPDATE order_drafts
        SET items_json = ?, subtotal = ?, discount_amount = ?, tax_amount = ?,
            deposit_required = ?, total_amount = ?, customer_notes = ?,
            status = ?, external_reference = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
      `).run(
        JSON.stringify(draft.items),
        draft.subtotal,
        draft.discount_amount || 0,
        draft.tax_amount || 0,
        draft.deposit_required || 0,
        draft.total_amount,
        draft.customer_notes || '',
        draft.status,
        draft.external_reference || null,
        draft.id
      );
    } else {
      this.db.prepare(`
        INSERT INTO order_drafts (
          id, session_id, tenant_id, status, draft_type, items_json,
          subtotal, discount_amount, tax_amount, deposit_required, total_amount,
          currency, customer_notes, idempotency_key, external_reference
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
      `).run(
        draft.id,
        draft.session_id,
        draft.tenant_id,
        draft.status || 'draft',
        draft.draft_type || 'product_order',
        JSON.stringify(draft.items),
        draft.subtotal,
        draft.discount_amount || 0,
        draft.tax_amount || 0,
        draft.deposit_required || 0,
        draft.total_amount,
        draft.currency,
        draft.customer_notes || '',
        draft.idempotency_key || null,
        draft.external_reference || null
      );
    }
    return this.getDraft(draft.id);
  }

  getDraft(draftId) {
    if (!draftId) return null;
    const row = this.db.prepare('SELECT * FROM order_drafts WHERE id = ?').get(draftId);
    if (!row) return null;
    try {
      row.items = JSON.parse(row.items_json);
    } catch (e) {
      row.items = [];
    }
    return row;
  }

  getLatestDraftForSession(sessionId) {
    const row = this.db.prepare(`
      SELECT * FROM order_drafts
      WHERE session_id = ?
      ORDER BY created_at DESC
      LIMIT 1
    `).get(sessionId);
    if (!row) return null;
    try {
      row.items = JSON.parse(row.items_json);
    } catch (e) {
      row.items = [];
    }
    return row;
  }

  confirmDraft(draftId, idempotencyKey = null) {
    return this.transaction(() => {
      const draft = this.getDraft(draftId);
      if (!draft) {
        throw new Error(`Draft ${draftId} does not exist.`);
      }

      if (draft.status === 'confirmed') {
        return { draft, alreadyConfirmed: true };
      }

      // Verify stock availability
      for (const item of draft.items) {
        const inv = this.getInventory(draft.tenant_id, item.product_id);
        if (inv && inv.stock_count < item.quantity) {
          throw new Error(`Item "${item.name}" is out of stock (Available: ${inv.stock_count}, Requested: ${item.quantity}). Cannot confirm draft.`);
        }
      }

      // Decrement inventory atomically
      for (const item of draft.items) {
        this.db.prepare(`
          UPDATE inventory
          SET stock_count = stock_count - ?, reserved_count = reserved_count + ?
          WHERE product_id = ? AND tenant_id = ?
        `).run(item.quantity, item.quantity, item.product_id, draft.tenant_id);
      }

      // Generate external confirmation reference
      const externalRef = `CONF-${draft.tenant_id.substring(0, 3).toUpperCase()}-${Date.now().toString(36).toUpperCase()}`;

      this.db.prepare(`
        UPDATE order_drafts
        SET status = 'confirmed', external_reference = ?, confirmed_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
      `).run(externalRef, draftId);

      // Audit log
      this.logAudit(draft.tenant_id, draft.session_id, 'DRAFT_CONFIRMED', 'customer', {
        draft_id: draftId,
        external_reference: externalRef,
        total_amount: draft.total_amount,
        currency: draft.currency
      });

      // Record BI Telemetry Event
      if (this.telemetry) {
        try {
          this.telemetry.recordEvent({
            tenantId: draft.tenant_id,
            sessionId: draft.session_id,
            eventType: 'DRAFT_CONFIRMED',
            category: draft.draft_type,
            draftId: draft.id,
            outcome: 'success',
            idempotencyKey: idempotencyKey || `EVT-CONF-${draftId}`,
            metadata: {
              external_reference: externalRef,
              total_amount: draft.total_amount,
              currency: draft.currency,
              items_count: draft.items.length
            }
          });
        } catch (e) {
          console.warn('[Telemetry] Non-fatal telemetry recording error on draft confirmation:', e.message);
        }
      }

      return { draft: this.getDraft(draftId), externalReference: externalRef, alreadyConfirmed: false };
    });
  }

  cancelDraft(draftId) {
    return this.transaction(() => {
      const draft = this.getDraft(draftId);
      if (!draft) throw new Error('Draft not found');

      if (draft.status === 'confirmed') {
        // Revert stock
        for (const item of draft.items) {
          this.db.prepare(`
            UPDATE inventory
            SET stock_count = stock_count + ?, reserved_count = reserved_count - ?
            WHERE product_id = ? AND tenant_id = ?
          `).run(item.quantity, item.quantity, item.product_id, draft.tenant_id);
        }
      }

      this.db.prepare(`
        UPDATE order_drafts
        SET status = 'cancelled', updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
      `).run(draftId);

      this.logAudit(draft.tenant_id, draft.session_id, 'DRAFT_CANCELLED', 'customer', { draft_id: draftId });

      // Record BI Telemetry Event
      if (this.telemetry) {
        try {
          this.telemetry.recordEvent({
            tenantId: draft.tenant_id,
            sessionId: draft.session_id,
            eventType: 'DRAFT_CANCELLED',
            category: draft.draft_type,
            draftId: draft.id,
            outcome: 'cancelled',
            metadata: {
              previous_status: draft.status,
              total_amount: draft.total_amount
            }
          });
        } catch (e) {
          console.warn('[Telemetry] Non-fatal telemetry recording error on draft cancellation:', e.message);
        }
      }

      return this.getDraft(draftId);
    });
  }

  // --- Audit Logging ---

  logAudit(tenantId, sessionId, action, actor, details = {}) {
    const id = `AUD-${Date.now()}-${Math.random().toString(36).substr(2, 6)}`;
    this.db.prepare(`
      INSERT INTO audit_logs (id, tenant_id, session_id, action, actor, details_json)
      VALUES (?, ?, ?, ?, ?, ?)
    `).run(id, tenantId, sessionId, action, actor, JSON.stringify(details));
  }

  getAuditLogs(tenantId, limit = 50) {
    return this.db.prepare(`
      SELECT * FROM audit_logs WHERE tenant_id = ? ORDER BY created_at DESC LIMIT ?
    `).all(tenantId, limit);
  }
}

// Singleton instance
const dbManager = new DatabaseManager();

module.exports = {
  dbManager,
  DatabaseManager
};
