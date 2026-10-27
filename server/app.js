/**
 * Express Application Setup
 */

const path = require('path');
require('dotenv').config();
const express = require('express');
const cors = require('cors');

const { rateLimiter, staticSecurity, errorHandler } = require('./middleware/security');
const chatRoutes = require('./routes/chatRoutes');
const draftRoutes = require('./routes/draftRoutes');
const tenantRoutes = require('./routes/tenantRoutes');
const handoffRoutes = require('./routes/handoffRoutes');
const analyticsRoutes = require('./routes/analyticsRoutes');

const app = express();

// Security & Parsing
app.use(cors());
app.use(express.json());
app.use(rateLimiter(120, 60 * 1000)); // 120 requests/min per IP

// 1. Global Path & Static Traversal Security Middleware
app.use(staticSecurity);

// 2. API Endpoints
app.use('/api', chatRoutes);
app.use('/api', draftRoutes);
app.use('/api', tenantRoutes);
app.use('/api', handoffRoutes);
app.use('/api', analyticsRoutes);

// Healthcheck
app.get('/api/health', (req, res) => {
  res.json({
    status: 'healthy',
    hasGeminiKey: !!process.env.GEMINI_API_KEY,
    geminiModel: process.env.GEMINI_MODEL || 'gemini-flash-lite-latest',
    timestamp: new Date().toISOString(),
    version: '2.4.0',
    service: 'Viral-X AI Sales Agent Production Core'
  });
});

// 3. Static Assets & Pages (Restricted Public Serving)
const rootDir = path.resolve(__dirname, '..');
const assetsDir = path.resolve(__dirname, '../assets');

// Whitelisted Public HTML Pages
const ALLOWED_HTML_PAGES = new Set([
  'index.html',
  'about.html',
  'services.html',
  'portfolio.html',
  'contact.html',
  'privacy.html',
  'terms.html',
  'chat.html',
  'service-ai-sales.html',
  'service-customer-intelligence.html',
  'service-google-maps.html',
  'service-web-development.html',
  'case-study-al-noor-jewelry.html',
  'case-study-kore-intelligence.html',
  'case-study-saffron-table.html',
  'case-study-vitalis-health.html'
]);

// Serve dedicated public assets (CSS, JS, images) strictly from assets directory
app.use('/assets', express.static(assetsDir, {
  dotfiles: 'deny',
  index: false,
  maxAge: '1d',
  setHeaders: (res) => {
    res.setHeader('X-Content-Type-Options', 'nosniff');
  }
}));

// Root route serves index.html
app.get('/', (req, res) => {
  res.sendFile(path.join(rootDir, 'index.html'));
});

// Serve whitelisted public HTML pages strictly from root
app.get('/:page', (req, res) => {
  let requestedPage = req.params.page;
  if (!requestedPage.endsWith('.html')) {
    requestedPage = `${requestedPage}.html`;
  }

  if (ALLOWED_HTML_PAGES.has(requestedPage)) {
    const safeFilePath = path.resolve(rootDir, requestedPage);
    if (safeFilePath.startsWith(rootDir) && !safeFilePath.includes('..')) {
      return res.sendFile(safeFilePath);
    }
  }

  res.status(404).json({ error: 'NotFound', message: 'The requested resource was not found.' });
});

// Catch-all 404 handler for unknown routes
app.use((req, res) => {
  res.status(404).json({
    error: 'NotFound',
    message: 'The requested resource was not found.'
  });
});

// Unified error handler
app.use(errorHandler);

module.exports = app;

