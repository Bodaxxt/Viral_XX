/**
 * Analytics & Telemetry API Routes (Sprint 2 Priority 3 & 4)
 * Exposes validated BI telemetry queries and demo event generator.
 */

const express = require('express');
const router = express.Router();
const { dbManager } = require('../db/database');
const { BI_EVENT_TYPES } = require('../analytics/telemetryService');

// Query telemetry events for a workspace
router.get('/analytics/events', (req, res, next) => {
  try {
    const { tenantId, eventType, sessionId, isDemo, limit, offset } = req.query;
    if (!tenantId) {
      return res.status(400).json({ error: 'tenantId is required.' });
    }

    const events = dbManager.telemetry.getEvents({
      tenantId,
      eventType: eventType || null,
      sessionId: sessionId || null,
      isDemo: isDemo !== undefined ? isDemo === 'true' || isDemo === '1' : null,
      limit: Number(limit) || 50,
      offset: Number(offset) || 0
    });

    res.json({
      tenantId,
      count: events.length,
      events
    });
  } catch (err) {
    next(err);
  }
});

// Telemetry summary & conversion telemetry
router.get('/analytics/summary', (req, res, next) => {
  try {
    const { tenantId, isDemo, days } = req.query;
    if (!tenantId) {
      return res.status(400).json({ error: 'tenantId is required.' });
    }

    const summary = dbManager.telemetry.getTelemetrySummary(tenantId, {
      isDemo: isDemo !== undefined ? isDemo === 'true' || isDemo === '1' : null,
      days: Number(days) || 30
    });

    res.json({
      success: true,
      summary
    });
  } catch (err) {
    next(err);
  }
});

// Funnel metrics endpoint
router.get('/analytics/funnel', (req, res, next) => {
  try {
    const { tenantId, isDemo, days } = req.query;
    if (!tenantId) {
      return res.status(400).json({ error: 'tenantId is required.' });
    }

    const funnel = dbManager.telemetry.getFunnelMetrics(tenantId, {
      isDemo: isDemo !== undefined ? isDemo === 'true' || isDemo === '1' : null,
      days: Number(days) || 30
    });

    res.json({
      success: true,
      funnel
    });
  } catch (err) {
    next(err);
  }
});

// Objection breakdown endpoint
router.get('/analytics/objections', (req, res, next) => {
  try {
    const { tenantId, isDemo, days } = req.query;
    if (!tenantId) {
      return res.status(400).json({ error: 'tenantId is required.' });
    }

    const objections = dbManager.telemetry.getObjectionBreakdown(tenantId, {
      isDemo: isDemo !== undefined ? isDemo === 'true' || isDemo === '1' : null,
      days: Number(days) || 30
    });

    res.json({
      success: true,
      objections
    });
  } catch (err) {
    next(err);
  }
});

// Unfulfilled demand signals endpoint
router.get('/analytics/demand', (req, res, next) => {
  try {
    const { tenantId, isDemo, days, limit } = req.query;
    if (!tenantId) {
      return res.status(400).json({ error: 'tenantId is required.' });
    }

    const demandSignals = dbManager.telemetry.getUnfulfilledDemandSignals(tenantId, {
      isDemo: isDemo !== undefined ? isDemo === 'true' || isDemo === '1' : null,
      days: Number(days) || 30,
      limit: Number(limit) || 10
    });

    res.json({
      success: true,
      demandSignals
    });
  } catch (err) {
    next(err);
  }
});

// Generate repeatable demo seed events for testing & dashboard preview
router.post('/analytics/events/demo-seed', (req, res, next) => {
  try {
    const { tenantId = 'al-noor-jewelry' } = req.body;
    const tenant = dbManager.getTenant(tenantId);
    if (!tenant) {
      return res.status(404).json({ error: `Tenant ${tenantId} not found.` });
    }

    const sessionId = `SES-SEED-${Date.now()}`;
    const generatedEvents = [];

    // 1. Product Search Event
    generatedEvents.push(dbManager.telemetry.recordEvent({
      tenantId,
      sessionId,
      eventType: BI_EVENT_TYPES.PRODUCT_SEARCH,
      category: 'search',
      outcome: 'success',
      isDemo: true,
      metadata: { query: 'diamond emerald collar', count: 2 }
    }));

    // 2. Unfulfilled Demand Event
    generatedEvents.push(dbManager.telemetry.recordEvent({
      tenantId,
      sessionId,
      eventType: BI_EVENT_TYPES.UNFULFILLED_DEMAND,
      category: 'search',
      outcome: 'no_results',
      isDemo: true,
      metadata: { query: 'platinum tennis bracelet under 5000', price_barrier: 5000 }
    }));

    // 3. Out of stock Event
    generatedEvents.push(dbManager.telemetry.recordEvent({
      tenantId,
      sessionId,
      eventType: BI_EVENT_TYPES.OUT_OF_STOCK_DETECTED,
      category: 'inventory',
      productId: 'J-104',
      sku: 'SKU-CUF-104',
      outcome: 'out_of_stock',
      isDemo: true,
      metadata: { location: 'Doha Place Vendôme Flagship' }
    }));

    // 4. Unanswered Question Event
    generatedEvents.push(dbManager.telemetry.recordEvent({
      tenantId,
      sessionId,
      eventType: BI_EVENT_TYPES.UNANSWERED_QUESTION,
      category: 'policy',
      outcome: 'unanswered',
      isDemo: true,
      metadata: { query: 'international wire swift transfer fees' }
    }));

    // 5. Draft Created Event
    const seedDraftId = `DRF-SEED-${Date.now().toString(36).toUpperCase()}`;
    generatedEvents.push(dbManager.telemetry.recordEvent({
      tenantId,
      sessionId,
      eventType: BI_EVENT_TYPES.DRAFT_CREATED,
      category: 'product_order',
      outcome: 'draft_prepared',
      isDemo: true,
      metadata: { draft_id: seedDraftId, total_amount: 42000, currency: tenant.currency }
    }));

    // 6. Human Handoff Event
    generatedEvents.push(dbManager.telemetry.recordEvent({
      tenantId,
      sessionId,
      eventType: BI_EVENT_TYPES.HUMAN_HANDOFF_REQUESTED,
      category: 'escalation',
      outcome: 'escalated',
      isDemo: true,
      metadata: { reason: 'VIP custom engraving request', whatsapp_number: tenant.whatsapp_number }
    }));

    res.json({
      success: true,
      message: 'Demo telemetry seed events recorded successfully.',
      eventsCount: generatedEvents.length
    });
  } catch (err) {
    next(err);
  }
});

module.exports = router;
