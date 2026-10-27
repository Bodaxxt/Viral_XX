/**
 * Production Security & Guardrails
 * - Prompt injection detection & neutralization
 * - System prompt extraction defense
 * - Input sanitization & sensitive data redaction
 * - Tenant isolation verification
 */

const INJECTION_PATTERNS = [
  /ignore\s+(all\s+)?(previous|prior|above)\s+instructions/i,
  /system\s+prompt/i,
  /reveal\s+(your\s+)?(instructions|prompt|secret|api\s*key)/i,
  /you\s+are\s+now\s+in\s+(developer|dan|jailbreak)\s+mode/i,
  /disregard\s+(any|all)\s+safety/i,
  /what\s+is\s+your\s+system\s+instruction/i,
  /print\s+your\s+initial\s+prompt/i,
  /bypass\s+(the\s+)?guardrails/i,
  /تجاهل\s+(جميع|كل)\s+التعليمات/i,
  /اكشف\s+(عن\s+)?التعليمات\s+السرية/i,
  /ما\s+هو\s+البرومبت\s+الرئيسي/i
];

class SecurityGuardrails {
  /**
   * Evaluates incoming text for prompt injection and malicious override attempts.
   */
  static inspectPrompt(input) {
    if (!input || typeof input !== 'string') {
      return { isSafe: true, sanitized: '' };
    }

    const trimmed = input.trim();
    for (const pattern of INJECTION_PATTERNS) {
      if (pattern.test(trimmed)) {
        return {
          isSafe: false,
          flaggedPattern: pattern.toString(),
          reason: 'PROMPT_INJECTION_DETECTED',
          safeResponse: 'I am the Viral-X verified sales assistant. I operate exclusively within our authorized business catalog, inventory verification, and customer ordering protocols. How can I assist you with our services today?'
        };
      }
    }

    return {
      isSafe: true,
      sanitized: trimmed.substring(0, 1000) // enforce reasonable token/character limit
    };
  }

  /**
   * Redacts sensitive payment and credential details before logging or external transmission.
   */
  static redactSensitive(text) {
    if (!text || typeof text !== 'string') return text;
    // Redact 16-digit card patterns
    let clean = text.replace(/\b\d{4}[ -]?\d{4}[ -]?\d{4}[ -]?\d{4}\b/g, '[REDACTED_CARD]');
    // Redact CVV patterns
    clean = clean.replace(/\b(cvv|cvc)[:\s]*\d{3,4}\b/gi, '$1: [REDACTED]');
    return clean;
  }

  /**
   * Enforces tenant isolation. Ensures that an entity requested strictly belongs to the authenticated tenant.
   */
  static verifyTenantAccess(requestedTenantId, activeTenantId) {
    if (!requestedTenantId || !activeTenantId) {
      throw new Error('Tenant ID cannot be null.');
    }
    if (requestedTenantId !== activeTenantId) {
      throw new Error(`Tenant Isolation Violation: Cross-tenant operation blocked (${requestedTenantId} !== ${activeTenantId}).`);
    }
    return true;
  }
}

module.exports = {
  SecurityGuardrails
};
