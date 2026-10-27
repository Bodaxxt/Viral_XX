/**
 * Chat API Routes
 */

const express = require('express');
const router = express.Router();
const { aiAgent } = require('../ai/aiAgent');
const { dbManager } = require('../db/database');

router.post('/chat', async (req, res, next) => {
  try {
    const { tenantId, sessionId, message, customerName } = req.body;

    if (!tenantId) {
      return res.status(400).json({ error: 'tenantId is required.' });
    }
    if (!message || typeof message !== 'string' || !message.trim()) {
      return res.status(400).json({ error: 'message string is required.' });
    }

    const session = sessionId || `SES-${Date.now()}-${Math.random().toString(36).substr(2, 6)}`;

    const result = await aiAgent.processMessage({
      tenantId,
      sessionId: session,
      userMessage: message,
      customerName
    });

    res.json({
      sessionId: session,
      tenantId,
      reply: result.reply,
      grounding: result.grounding,
      toolCalls: result.toolCalls || [],
      hasDraftOrder: result.hasDraftOrder || null,
      isHandoff: result.isHandoff || false,
      whatsappUrl: result.whatsappUrl || null
    });
  } catch (err) {
    next(err);
  }
});

router.get('/chat/history/:sessionId', (req, res, next) => {
  try {
    const { sessionId } = req.params;
    const messages = dbManager.getSessionMessages(sessionId, 50);
    res.json({ sessionId, messages });
  } catch (err) {
    next(err);
  }
});

module.exports = router;
