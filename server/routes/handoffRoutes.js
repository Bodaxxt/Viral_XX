/**
 * Human Handoff Routes
 * Builds authenticated WhatsApp escalation payloads with full customer context.
 */

const express = require('express');
const router = express.Router();
const { toolExecutor } = require('../tools/toolRegistry');

router.post('/handoff/whatsapp', async (req, res, next) => {
  try {
    const { tenantId, sessionId, reason, notes } = req.body;
    if (!tenantId) {
      return res.status(400).json({ error: 'tenantId is required.' });
    }

    const result = await toolExecutor.execute('request_human_handoff', {
      reason: reason || 'Customer requested live specialist communication',
      notes: notes || ''
    }, { tenantId, sessionId });

    res.json({
      success: true,
      ...result
    });
  } catch (err) {
    next(err);
  }
});

module.exports = router;
