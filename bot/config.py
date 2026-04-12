"""Bot configuration loaded from environment variables.

Reads the same .env used by the FastAPI app. All Telegram-related
variables share the TELEGRAM_ prefix (already present in .env).
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class BotSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Telegram Bot API
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_WEBHOOK_SECRET: str = ""      # X-Telegram-Bot-Api-Secret-Token
    TELEGRAM_WEBHOOK_BASE_URL: str = ""    # https://yourdomain.com
    TELEGRAM_BOT_PORT: int = 8443          # internal webhook port

    # Web App URL base (for Telegram WebApp links to the platform)
    APP_BASE_URL: str = "http://localhost:8000"

    # Database (same PostgreSQL instance as FastAPI app)
    DATABASE_URL: str = "postgresql+asyncpg://seo:seo@postgres:5432/seo"

    # Redis (same Redis instance; used for Celery broker)
    REDIS_URL: str = "redis://redis:6379/0"

    # Logging
    LOG_LEVEL: str = "INFO"


settings = BotSettings()
