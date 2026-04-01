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

    # App
    DB_ECHO: bool = False
    LOG_LEVEL: str = "INFO"


settings = Settings()
