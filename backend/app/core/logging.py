"""
Viral-X Structured Logging & Secret Redaction
Sprint 2.5 Migration Foundation
"""

import logging
import re
import sys
from typing import Any
from backend.app.core.config import settings

# Sensitive data redaction patterns (matching SecurityGuardrails)
CARD_PATTERN = re.compile(r"\b(?:\d[ -]*?){13,19}\b")
AUTH_PATTERN = re.compile(r"(?i)(api[_-]?key|bearer|token|secret|password)\s*[:=]\s*['\"]?([^\s'\"]+)['\"]?")
JWT_PATTERN = re.compile(r"\beyJ[a-zA-Z0-9_-]{10,}\.eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]+\b")
BEARER_PATTERN = re.compile(r"(?i)\bBearer\s+[a-zA-Z0-9_.-]+")
JSON_SECRET_PATTERN = re.compile(r'(?i)"(password|token|secret|access_token|refresh_token|jwt_secret_key)"\s*:\s*"[^"]+"')


class SensitiveDataFilter(logging.Filter):
    """
    Redacts credit card numbers, JWT tokens, Bearer credentials, and authentication secrets.
    """
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = self._redact(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: self._redact(v) if isinstance(v, str) else v for k, v in record.args.items()}
            elif isinstance(record.args, tuple):
                record.args = tuple(self._redact(v) if isinstance(v, str) else v for v in record.args)
        return True

    @staticmethod
    def _redact(text: str) -> str:
        # Redact credit card patterns
        text = CARD_PATTERN.sub("[REDACTED_CARD]", text)
        # Redact JWT tokens
        text = JWT_PATTERN.sub("[REDACTED_TOKEN]", text)
        # Redact Bearer header tokens
        text = BEARER_PATTERN.sub("Bearer [REDACTED_TOKEN]", text)
        # Redact JSON secret fields
        text = JSON_SECRET_PATTERN.sub(r'"\1": "[REDACTED_SECRET]"', text)
        # Redact api tokens and credentials key-values
        text = AUTH_PATTERN.sub(r"\1: [REDACTED_CREDENTIAL]", text)
        return text


def setup_logging() -> logging.Logger:
    """
    Configures application-wide logging with sensitivity filtering.
    """
    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-7s | [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    handler.addFilter(SensitiveDataFilter())

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Avoid adding duplicate handlers if setup_logging is called multiple times
    if not root_logger.handlers:
        root_logger.addHandler(handler)
    else:
        root_logger.handlers = [handler]

    logger = logging.getLogger("viral_x")
    logger.info(
        "Logging initialized for %s in %s environment (level=%s)",
        settings.APP_NAME,
        settings.ENVIRONMENT,
        settings.LOG_LEVEL
    )
    return logger


logger = setup_logging()
