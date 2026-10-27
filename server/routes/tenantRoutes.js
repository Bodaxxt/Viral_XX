/**
 * Tenant & Integration Metadata Routes
 */

const express = require('express');
const router = express.Router();
const { dbManager } = require('../db/database');
const { integrationRegistry } = require('../adapters/externalIntegrations');

router.get('/tenants', (req, res, next) => {
  try {
    const list = dbManager.listTenants();
    res.json({ tenants: list });
  } catch (err) {
    next(err);
  }
});

router.get('/tenants/:tenantId', (req, res, next) => {
  try {
    const { tenantId } = req.params;
    const tenant = dbManager.getTenant(tenantId);
    if (!tenant) {
      return res.status(404).json({ error: `Tenant ${tenantId} not found.` });
    }
    res.json({ tenant });
  } catch (err) {
    next(err);
  }
});

router.get('/tenants/:tenantId/catalog', (req, res, next) => {
  try {
    const { tenantId } = req.params;
    const products = dbManager.searchProducts(tenantId, '', '');
    res.json({ tenantId, products });
  } catch (err) {
    next(err);
  }
});

router.get('/integrations', (req, res, next) => {
  try {
    const statuses = integrationRegistry.getAllStatuses();
    res.json({ integrations: statuses });
  } catch (err) {
    next(err);
  }
});

module.exports = router;
