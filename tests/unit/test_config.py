"""
Unit Tests for NEXUS Configuration Module
Tests environment settings resolution and defaults.
"""

from apps.api.config import Settings


def test_default_settings():
    settings = Settings(_env_file=None, DATABASE_URL=None, ENVIRONMENT="development")
    assert settings.PROJECT_NAME == "NEXUS"
    assert settings.API_PORT == 8080
    assert settings.API_V1_PREFIX == "/api/v1"
    assert settings.ENVIRONMENT == "development"


def test_database_url_resolution():
    settings = Settings(
        _env_file=None,
        DATABASE_URL=None,
        POSTGRES_USER="test_u",
        POSTGRES_PASSWORD="test_p",
        POSTGRES_HOST="db_host",
        POSTGRES_PORT=5434,
        POSTGRES_DB="test_db"
    )
    url = settings.get_database_url()
    assert "postgresql://test_u:test_p@db_host:5434/test_db" in url


def test_custom_database_url_override():
    custom_url = "sqlite:///./custom_nexus.db"
    settings = Settings(_env_file=None, DATABASE_URL=custom_url)
    assert settings.get_database_url() == custom_url
