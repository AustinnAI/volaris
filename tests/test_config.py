"""
Test Configuration Module
"""

import pytest

from app.config import Settings


def test_settings_validation():
    """Test settings validation"""
    settings = Settings(
        ENVIRONMENT="development",
        DATABASE_URL="postgresql://test:test@localhost/test",
        UPSTASH_REDIS_REST_URL="https://test.upstash.io",
        UPSTASH_REDIS_REST_TOKEN="test_token",
    )

    assert settings.ENVIRONMENT == "development"
    assert settings.LOG_LEVEL == "INFO"


def test_environment_validation():
    """Test environment validation"""
    with pytest.raises(ValueError):
        Settings(
            ENVIRONMENT="invalid",
            DATABASE_URL="postgresql://test:test@localhost/test",
            UPSTASH_REDIS_REST_URL="https://test.upstash.io",
            UPSTASH_REDIS_REST_TOKEN="test_token",
        )


def test_is_production_flag():
    """Test production environment flag"""
    settings = Settings(
        ENVIRONMENT="production",
        DATABASE_URL="postgresql://test:test@localhost/test",
        UPSTASH_REDIS_REST_URL="https://test.upstash.io",
        UPSTASH_REDIS_REST_TOKEN="test_token",
    )

    assert settings.is_production is True
    assert settings.is_development is False
