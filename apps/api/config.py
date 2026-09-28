"""
NEXUS Configuration Module
Handles environment variables and system settings with Pydantic BaseSettings.
"""

from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    # Application & Environment
    PROJECT_NAME: str = "NEXUS"
    PROJECT_VERSION: str = "0.1.0"
    ENVIRONMENT: str = Field(default="development", description="Environment: development, test, production")
    DEBUG: bool = Field(default=True, description="Debug mode")
    LOG_LEVEL: str = Field(default="INFO", description="Log level")

    # API Gateway
    API_V1_PREFIX: str = "/api/v1"
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8080
    API_SECRET_KEY: str = Field(default="change_this_to_a_secure_random_32_byte_secret_key", min_length=16)
    API_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours

    # Database Settings (PostgreSQL with SQLite test fallback)
    POSTGRES_USER: str = "nexus_user"
    POSTGRES_PASSWORD: str = "nexus_secure_password"
    POSTGRES_DB: str = "nexus_db"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5434
    DATABASE_URL: Optional[str] = None

    # Redis Cache & PubSub
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0

    # Mosquitto MQTT Telemetry Broker
    MQTT_BROKER_HOST: str = "localhost"
    MQTT_BROKER_PORT: int = 1884
    MQTT_TOPIC_TELEMETRY: str = "nexus/telemetry/+"
    MQTT_TOPIC_COMMANDS: str = "nexus/commands/+"

    # Synthetic Simulator Defaults
    SIMULATOR_ENABLED: bool = True
    SIMULATOR_TICK_SECONDS: float = 1.0
    SIMULATOR_NOISE_STD: float = 0.02
    SIMULATOR_AUTO_DEGRADE: bool = False

    # Machine Learning & Anomaly Detection Parameters
    ANOMALY_SENSITIVITY: float = 0.85
    PREDICTION_HORIZON_STEPS: int = 120
    RUL_BASE_HOURS: float = 2400.0

    # Frontend Config
    FRONTEND_PORT: int = 5180
    CORS_ORIGINS: list[str] = [
        "http://localhost:5180",
        "http://127.0.0.1:5180",
        "http://localhost:3000",
        "http://127.0.0.1:3000"
    ]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

    def get_database_url(self) -> str:
        """Returns the configured database URL or generates one from Postgres params."""
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"


@lru_cache()
def get_settings() -> Settings:
    """Returns cached settings instance."""
    return Settings()
