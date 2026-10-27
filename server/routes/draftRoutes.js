/**
 * Order & Booking Draft Routes
 * Manages verified customer confirmation, cancellation, and idempotency protection.
 */

const express = require('express');
const router = express.Router();
const { dbManager } = require('../db/database');

router.get('/drafts/:draftId', (req, res, next) => {
  try {
    const { draftId } = req.params;
    const draft = dbManager.getDraft(draftId);
    if (!draft) {
      return res.status(404).json({ error: 'Draft not found.' });
    }
    res.json({ draft });
  } catch (err) {
    next(err);
  }
});

router.post('/drafts/confirm', (req, res, next) => {
  try {
    const { draftId, idempotencyKey } = req.body;
    if (!draftId) {
      return res.status(400).json({ error: 'draftId is required.' });
    }

    const result = dbManager.confirmDraft(draftId, idempotencyKey);
    res.json({
      success: true,
      alreadyConfirmed: result.alreadyConfirmed,
      externalReference: result.externalReference || result.draft.external_reference,
      draft: result.draft,
      message: result.alreadyConfirmed
        ? 'This order draft was previously confirmed.'
        : 'Draft confirmed successfully. Inventory reserved and transmitted to merchant fulfillment.'
    });
  } catch (err) {
    res.status(400).json({
      success: false,
      error: err.message
    });
  }
});

router.post('/drafts/cancel', (req, res, next) => {
  try {
    const { draftId } = req.body;
    if (!draftId) {
      return res.status(400).json({ error: 'draftId is required.' });
    }

    const draft = dbManager.cancelDraft(draftId);
    res.json({
      success: true,
      draft,
      message: 'Draft order has been cancelled.'
    });
  } catch (err) {
    next(err);
  }
});

module.exports = router;
