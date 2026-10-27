const path = require('path');

const rateLimitMap = new Map();

function rateLimiter(limit = 60, windowMs = 60 * 1000) {
  return (req, res, next) => {
    const ip = req.ip || req.headers['x-forwarded-for'] || req.socket.remoteAddress || 'unknown';
    const now = Date.now();
    const entry = rateLimitMap.get(ip) || { count: 0, resetTime: now + windowMs };

    if (now > entry.resetTime) {
      entry.count = 1;
      entry.resetTime = now + windowMs;
    } else {
      entry.count += 1;
    }

    rateLimitMap.set(ip, entry);

    if (entry.count > limit) {
      return res.status(429).json({
        error: 'Too Many Requests',
        message: 'Rate limit exceeded. Please wait before sending further requests.'
      });
    }

    next();
  };
}

/**
 * Static File & Path Security Middleware (Sprint 2 Priority 1)
 * Restricts static file access to allowed public directories and files.
 * Rejects path traversal, encoded separators, and access to sensitive files.
 */
function staticSecurity(req, res, next) {
  const rawUrl = req.url || '';
  const originalUrl = req.originalUrl || '';

  // 1. Decode requested path safely
  let decodedPath;
  try {
    decodedPath = decodeURIComponent(req.path);
  } catch {
    return res.status(400).json({ error: 'BadRequest', message: 'Malformed URL encoding.' });
  }

  let decodedRaw = rawUrl;
  try {
    decodedRaw = decodeURIComponent(rawUrl);
  } catch {
    return res.status(400).json({ error: 'BadRequest', message: 'Malformed URL encoding.' });
  }

  // Normalize path
  const normalized = path.normalize(decodedPath).replace(/\\/g, '/');
  const lowerPath = normalized.toLowerCase();
  const lowerRaw = rawUrl.toLowerCase();
  const lowerDecodedRaw = decodedRaw.toLowerCase();
  const lowerOriginal = originalUrl.toLowerCase();

  // 2. Traversal & dangerous character check (applies globally across all routes)
  if (
    decodedPath.includes('..') ||
    normalized.includes('..') ||
    lowerRaw.includes('..') ||
    lowerDecodedRaw.includes('..') ||
    lowerOriginal.includes('..') ||
    lowerRaw.includes('%2e%2e') ||
    lowerOriginal.includes('%2e%2e') ||
    lowerRaw.includes('%252e') ||
    lowerOriginal.includes('%252e') ||
    lowerRaw.includes('\\') ||
    lowerDecodedRaw.includes('\\') ||
    lowerOriginal.includes('\\') ||
    lowerRaw.includes('%5c') ||
    lowerOriginal.includes('%5c') ||
    decodedPath.includes('\0') ||
    lowerRaw.includes('%00') ||
    lowerOriginal.includes('%00')
  ) {
    return res.status(403).json({
      error: 'Forbidden',
      message: 'Path traversal attempt detected and blocked.'
    });
  }

  // If this is an API route, allow it to pass through to the router
  if (req.path.startsWith('/api')) {
    return next();
  }

  // 3. Deny access to sensitive files, extensions, and internal directories
  const blockedPatterns = [
    /^\/\./,                                // Root hidden files (e.g. /.env, /.git)
    /\/\./,                                 // Nested hidden files (e.g. /foo/.env)
    /\.env(\..+)?$/,                        // .env, .env.example, .env.local, etc.
    /\.(db|sqlite|sqlite3|db-wal|db-shm)$/, // SQLite database files
    /\.sql$/,                               // SQL files
    /package(-lock)?\.json$/,               // Package manifests
    /\.(md|markdown|log)$/,                 // Markdown docs, audit logs
    /\.(yml|yaml|ini|conf|config)$/,        // Config files
    /^\/(server|node_modules|docs|tests|\.git|\.system_generated|\.gemini)(\/|$)/ // Backend directories
  ];

  for (const pattern of blockedPatterns) {
    if (pattern.test(lowerPath)) {
      return res.status(404).json({
        error: 'NotFound',
        message: 'The requested resource was not found.'
      });
    }
  }

  next();
}

function errorHandler(err, req, res, next) {
  console.error('[API Error]:', err);
  const status = err.status || 500;
  res.status(status).json({
    error: err.name || 'InternalServerError',
    message: err.message || 'An unexpected server error occurred.'
  });
}

module.exports = {
  rateLimiter,
  staticSecurity,
  errorHandler
};

