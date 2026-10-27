"""
Tests for Core Configuration and Secret Masking
"""

import os
from unittest.mock import patch
from backend.app.core.config import Settings


def test_default_config_properties():
    settings = Settings()
    assert settings.APP_NAME == "Viral-X AI Sales Agent & BI Platform"
    assert settings.MAX_REQUEST_SIZE_BYTES == 1_048_576
    assert settings.REQUEST_TIMEOUT_SECONDS == 30.0
    assert "http://localhost:3000" in settings.cors_origin_list
    assert settings.is_sqlite is True


def test_secret_repr_masking():
    settings = Settings(
        GEMINI_API_KEY="secret-gemini-key",
        OPENAI_API_KEY="secret-openai-key",
        ANTHROPIC_API_KEY="secret-anthropic-key",
    )
    repr_str = repr(settings)
    assert "secret-gemini-key" not in repr_str
    assert "secret-openai-key" not in repr_str
    assert "secret-anthropic-key" not in repr_str


def test_database_url_resolution():
    with patch.dict(os.environ, {"DATABASE_URL": "sqlite:///./custom.db"}):
        s = Settings()
        assert "custom.db" in s.effective_database_url
