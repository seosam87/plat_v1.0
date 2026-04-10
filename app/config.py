from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    DATABASE_URL: str
    SYNC_DATABASE_URL: str

    # Redis
    REDIS_URL: str

    # JWT
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    # Celery
    CELERY_WORKER_CONCURRENCY: int = 8

    # Fernet key for WP Application Password encryption
    # Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    FERNET_KEY: str

    # Crawler
    CRAWLER_DELAY_MS: int = 500
    CRAWLER_MAX_PAGES: int = 500

    # Google Search Console OAuth 2.0
    GSC_CLIENT_ID: str = ""
    GSC_CLIENT_SECRET: str = ""
    GSC_REDIRECT_URI: str = "http://localhost:8000/auth/gsc/callback"

    # DataForSEO
    DATAFORSEO_LOGIN: str = ""
    DATAFORSEO_PASSWORD: str = ""

    # Yandex Webmaster
    YANDEX_WEBMASTER_TOKEN: str = ""

    # Playwright SERP
    SERP_MAX_DAILY_REQUESTS: int = 50
    SERP_DELAY_MS: int = 3000

    # Telegram alerts
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""
    TELEGRAM_BOT_USERNAME: str = ""
    TELEGRAM_CHANNEL_ID: str = ""  # e.g. @mychannel or -100123456789
    POSITION_DROP_THRESHOLD: int = 5  # alert if keyword drops by this many positions

    # Proxy & anticaptcha for SERP parsing
    PROXY_URL: str = ""
    ANTICAPTCHA_KEY: str = ""
    SERP_DAILY_LIMIT: int = 200

    # XMLProxy
    XMLPROXY_LOW_BALANCE_THRESHOLD: int = 50  # Alert when balance drops below this (RUB)

    # SMTP
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = ""

    # App
    DB_ECHO: bool = False
    LOG_LEVEL: str = "INFO"
    APP_URL: str = "http://localhost:8000"


settings = Settings()
