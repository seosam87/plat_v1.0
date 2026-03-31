# Phase 1 Research: Stack & Auth

**Phase:** 1 of 11 — Stack & Auth
**Requirements covered:** INFRA-01, INFRA-05, INFRA-06, INFRA-07, AUTH-01, AUTH-02, AUTH-05, SEC-01, SEC-03, SEC-04
**Researched:** 2026-03-31

---

## 01-01: Docker Compose Stack

### Service Topology

The stack needs five services minimum in `docker-compose.yml`:

| Service | Image | Role |
|---------|-------|------|
| `api` | custom `python:3.12-slim` | FastAPI + uvicorn |
| `postgres` | `postgres:16-alpine` | Primary database |
| `redis` | `redis:7.2-alpine` | Broker + result backend |
| `worker` | same as `api` | Celery worker (all 3 queues) |
| `beat` | same as `api` | Celery Beat scheduler |

A `flower` service (port 5555) can be added but is deferred to Phase 11. For Phase 1, the three-queue topology must be wired and verified in logs even with a single worker container.

### docker-compose.yml Structure

```yaml
version: "3.9"

services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
      interval: 5s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  redis:
    image: redis:7.2-alpine
    command: >
      redis-server
      --appendonly yes
      --maxmemory 512mb
      --maxmemory-policy allkeys-lru
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5
    restart: unless-stopped

  api:
    build: .
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    env_file: .env
    ports:
      - "8000:8000"
    volumes:
      - ./app:/app/app
      - ./logs:/app/logs
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    restart: unless-stopped

  worker:
    build: .
    command: >
      celery -A app.celery_app worker
      --loglevel=info
      --queues=crawl,wp,default
      --concurrency=${CELERY_WORKER_CONCURRENCY:-8}
    env_file: .env
    volumes:
      - ./logs:/app/logs
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    restart: unless-stopped

  beat:
    build: .
    command: celery -A app.celery_app beat --loglevel=info --scheduler redbeat.schedulers.RedBeatScheduler
    env_file: .env
    depends_on:
      redis:
        condition: service_healthy
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
```

**Key decisions:**
- Health checks on `postgres` and `redis` with `condition: service_healthy` in `depends_on` — prevents race conditions on cold start (INFRA-01).
- `--appendonly yes` on Redis ensures Beat schedule persists across Redis restarts.
- `maxmemory-policy allkeys-lru` prevents Redis OOM from Celery result accumulation (Pitfall 4).
- `CELERY_WORKER_CONCURRENCY` env var makes worker count configurable without code changes (INFRA-07).
- Named volumes without `external: true` for now (safe for dev); Phase 11 can harden to external volumes.

### FastAPI Lifespan Pattern (not on_event)

`on_event("startup")` is deprecated and removed in FastAPI 0.115. The only correct pattern is `@asynccontextmanager` lifespan:

```python
# app/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.database import engine
from app.config import settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: initialize DB engine, verify connection
    async with engine.begin() as conn:
        pass  # pool warms up; replace with actual startup logic
    yield
    # Shutdown: dispose engine cleanly
    await engine.dispose()

app = FastAPI(lifespan=lifespan, title="SEO Management Platform")
```

Do NOT use `@app.on_event("startup")` — it raises a deprecation warning on 0.111 and is removed on 0.115.

### SQLAlchemy 2.0 Async Session Setup

```python
# app/database.py
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from app.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,  # postgresql+asyncpg://...
    pool_size=10,
    max_overflow=5,
    pool_timeout=30,
    pool_pre_ping=True,  # detects dead connections before use
    echo=settings.DB_ECHO,  # False in prod, True in dev for SQL logging
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,  # objects remain accessible after commit
)

class Base(DeclarativeBase):
    pass
```

**The get_db dependency — critical pattern:**

```python
# app/dependencies.py
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import AsyncSessionLocal

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        # AsyncSessionLocal() context manager calls session.close() on exit
        # No explicit finally needed — the async with handles it
```

The `async with AsyncSessionLocal() as session` pattern ensures `session.close()` is always called even on exceptions (via the context manager's `__aexit__`). The `try/except` block adds explicit rollback on error. This prevents connection leaks (Pitfall 6).

**Never** pass this session to Celery tasks or `BackgroundTask` — they get their own sessions.

### Pydantic-Settings 2.x Config

```python
# app/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    DATABASE_URL: str  # postgresql+asyncpg://user:pass@postgres:5432/dbname
    SYNC_DATABASE_URL: str  # postgresql+psycopg2://user:pass@postgres:5432/dbname (for Celery)

    # Redis
    REDIS_URL: str  # redis://redis:6379/0

    # JWT
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24h

    # Celery
    CELERY_WORKER_CONCURRENCY: int = 8

    # App
    DB_ECHO: bool = False

settings = Settings()
```

`BaseSettings` in Pydantic v2 lives in `pydantic-settings` package (separate install). The `model_config` pattern replaces the inner `class Config` from Pydantic v1.

### Three Celery Queues

```python
# app/celery_app.py
from celery import Celery
from app.config import settings

celery_app = Celery(
    "seo_platform",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.tasks.crawl_tasks", "app.tasks.wp_tasks", "app.tasks.default_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    result_expires=3600,  # 1h — prevents Redis bloat (Pitfall 4)
    task_acks_late=True,  # acknowledge after completion, not on receipt
    task_track_started=True,
    worker_prefetch_multiplier=1,  # don't prefetch extra tasks on Playwright workers
    task_routes={
        "app.tasks.crawl_tasks.*": {"queue": "crawl"},
        "app.tasks.wp_tasks.*": {"queue": "wp"},
        "app.tasks.default_tasks.*": {"queue": "default"},
    },
    task_default_queue="default",
)
```

Queue concurrency strategy:
- `crawl` queue: `concurrency=2` — Playwright-heavy, RAM-constrained
- `wp` queue: `concurrency=4` — network I/O, moderate concurrency
- `default` queue: `concurrency=8` — fast tasks, high throughput

For Phase 1, all queues run on a single worker with the combined concurrency setting from `CELERY_WORKER_CONCURRENCY`. Separate worker services per queue can be added in Phase 11.

### .env.example Structure

```bash
# Database
POSTGRES_USER=seo_user
POSTGRES_PASSWORD=changeme
POSTGRES_DB=seo_platform
DATABASE_URL=postgresql+asyncpg://seo_user:changeme@postgres:5432/seo_platform
SYNC_DATABASE_URL=postgresql+psycopg2://seo_user:changeme@postgres:5432/seo_platform

# Redis
REDIS_URL=redis://redis:6379/0

# JWT
SECRET_KEY=generate-with-openssl-rand-hex-32
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# Celery
CELERY_WORKER_CONCURRENCY=8

# App
DB_ECHO=false

# Logging
LOG_LEVEL=INFO
```

The `SECRET_KEY` must never have a real value in `.env.example`. Add `.env` to `.gitignore`. Pre-commit hook should reject commits where `.env` is staged.

---

## 01-02: Alembic + Auth

### Alembic Async Setup

Alembic 1.13 supports SQLAlchemy 2.0 async engines, but `env.py` needs explicit async handling:

```python
# alembic/env.py (key async sections)
import asyncio
from sqlalchemy.ext.asyncio import async_engine_from_config
from app.database import Base
from app.config import settings

# Import all models so Alembic can detect them
from app.models import user  # noqa: F401

def run_migrations_offline() -> None:
    url = settings.DATABASE_URL
    context.configure(url=url, target_metadata=Base.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()

def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()

async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()

if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
```

`NullPool` is required in Alembic's async `env.py` — it prevents connection pool lifecycle conflicts between Alembic's migration run and the regular pool.

### Users Table Model

```python
# app/models/user.py
import uuid
from datetime import datetime
from enum import Enum as PyEnum
from sqlalchemy import String, Boolean, DateTime, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base

class UserRole(str, PyEnum):
    admin = "admin"
    manager = "manager"
    client = "client"

class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(SAEnum(UserRole), nullable=False, default=UserRole.client)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
```

Use `UUID(as_uuid=True)` with asyncpg — it natively serializes Python `uuid.UUID` objects. The `Mapped[T]` + `mapped_column()` style is the SQLAlchemy 2.0 typed API; do not use 1.x column-class style.

### bcrypt Password Hashing

```python
# app/auth/password.py
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)

def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)
```

Cost factor 12 is the 2025 recommendation — it takes ~250ms on modern hardware, which is slow enough to deter brute force but fast enough for a login endpoint. Never log `plain` passwords anywhere.

### JWT Issue and Verify

```python
# app/auth/jwt.py
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from app.config import settings

def create_access_token(user_id: str, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "role": role,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

def decode_access_token(token: str) -> dict:
    """Raises JWTError on invalid/expired token."""
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
```

`python-jose` with `[cryptography]` extra is the chosen library. Include `role` in the JWT payload so the current-user dependency can enforce RBAC without a DB lookup on every request.

### Current-User FastAPI Dependency

```python
# app/auth/dependencies.py
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from jose import JWTError
from app.auth.jwt import decode_access_token
from app.dependencies import get_db
from app.models.user import User, UserRole
from app.services.user_service import get_user_by_id

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = await get_user_by_id(db, user_id)
    if user is None or not user.is_active:
        raise credentials_exception
    return user

async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user
```

`OAuth2PasswordBearer` expects the token in the `Authorization: Bearer <token>` header. The `tokenUrl` should match the login endpoint path.

### Login Endpoint

```python
# app/routers/auth.py
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from app.dependencies import get_db
from app.auth.password import verify_password
from app.auth.jwt import create_access_token
from app.services.user_service import get_user_by_email

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/token")
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    user = await get_user_by_email(db, form_data.username)  # OAuth2 form uses "username" field
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Account deactivated")

    token = create_access_token(str(user.id), user.role.value)
    return {"access_token": token, "token_type": "bearer"}
```

`OAuth2PasswordRequestForm` expects form body with `username` and `password` fields — this is the OAuth2 spec. The form field named "username" can hold an email address; the application maps it to email lookup.

---

## 01-03: RBAC

### Role Enum Design

Three roles with explicit privilege hierarchy:

```
admin > manager > client
```

- **admin**: full platform access, user management, all sites
- **manager**: manages sites and projects they own; cannot see other managers' data
- **client**: read-only access to projects explicitly assigned to them

The `UserRole` enum is defined on the `User` model (see 01-02 above). It maps to a PostgreSQL `ENUM` type via `SAEnum(UserRole)`.

### Role Guard Dependencies

```python
# app/auth/dependencies.py (role guards)
from functools import partial

def require_role(*allowed_roles: UserRole):
    """Factory: returns a dependency that checks the current user's role."""
    async def _check(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user
    return _check

# Pre-built dependencies for common checks
require_admin = require_role(UserRole.admin)
require_manager_or_above = require_role(UserRole.admin, UserRole.manager)
require_any_role = require_role(UserRole.admin, UserRole.manager, UserRole.client)
```

Usage in routes:

```python
@router.get("/admin/users")
async def list_users(current_user: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    ...
```

### Service-Layer Role Enforcement (SEC-04)

Route-level checks alone are insufficient — services must also enforce role boundaries. The pattern is to pass `current_user` as an explicit parameter:

```python
# app/services/user_service.py
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User, UserRole
from fastapi import HTTPException, status

async def get_user_by_id(db: AsyncSession, user_id: str) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()

async def list_users(db: AsyncSession, current_user: User) -> list[User]:
    """Only admins can list all users."""
    if current_user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Admin only")
    result = await db.execute(select(User).order_by(User.created_at))
    return result.scalars().all()

async def deactivate_user(db: AsyncSession, target_user_id: str, current_user: User) -> User:
    """Admin-only: deactivate another user."""
    if current_user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Admin only")
    user = await get_user_by_id(db, target_user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_active = False
    await db.flush()
    return user
```

The service raises `HTTPException` directly — this is acceptable because the service is always called from within a FastAPI request context in Phase 1. For Celery tasks calling services in later phases, the service layer should raise domain-specific exceptions that the task layer converts.

### Admin User Management Endpoints

```
GET    /admin/users          — list all users (admin only)
POST   /admin/users          — create user (admin only)
PUT    /admin/users/{id}     — edit user (admin only)
DELETE /admin/users/{id}     — deactivate user (admin only; soft delete via is_active=False)
```

No hard deletes — users are deactivated (`is_active=False`), not deleted, to preserve audit log integrity.

---

## 01-04: Audit Log + Logging

### Audit Log Model

```python
# app/models/audit_log.py
import uuid
from datetime import datetime
from typing import Any
from sqlalchemy import String, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entity_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    detail_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False, index=True
    )
```

- `user_id` nullable with `SET NULL` on user deletion — audit log must survive user deactivation.
- `detail_json` as JSONB — flexible for arbitrary event detail without schema changes.
- Index on `(user_id, created_at)` for user activity queries; index on `(action, created_at)` for action type queries.

### Audit Log Service

```python
# app/services/audit_service.py
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.audit_log import AuditLog
import uuid

async def log_action(
    db: AsyncSession,
    action: str,
    user_id: uuid.UUID | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    detail: dict | None = None,
) -> None:
    """Write an audit log entry. Call from service functions, not route handlers."""
    entry = AuditLog(
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id else None,
        detail_json=detail,
    )
    db.add(entry)
    # Does not commit — caller's session commits; audit log is part of the same transaction
```

Audit entries share the request transaction — if the main operation rolls back, the audit entry also rolls back. This is correct behavior: you don't want audit logs for failed operations cluttering the table. For critical security events (failed logins, blocked access), log to the structured application log (loguru) as well.

### Middleware vs. Dependency for Audit Logging

Two approaches exist:

1. **Starlette middleware**: intercepts every request/response automatically. Hard to access the result of the business operation (e.g., the new user ID after creation). Must parse request body, which requires buffering.

2. **Explicit service-layer calls**: `audit_service.log_action(db, ...)` called inside service functions after the operation succeeds.

**Recommendation: explicit service-layer calls.** This is simpler, captures the exact event context (new entity ID, old values), and does not require request body buffering. Reserve middleware for cross-cutting concerns like request timing and correlation ID injection.

For Phase 1, implement `log_action()` in the service layer for these events (AUTH-05):
- User login (success + failure)
- User created, edited, deactivated
- Role changed

### loguru Setup

```python
# app/logging_config.py
import sys
from loguru import logger

def setup_logging(log_level: str = "INFO") -> None:
    logger.remove()  # remove default stderr sink

    # Human-readable stderr for development
    logger.add(
        sys.stderr,
        level=log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{line}</cyan> — <level>{message}</level>",
    )

    # JSON file sink for production (INFRA-05)
    logger.add(
        "logs/app.log",
        level="DEBUG",
        serialize=True,       # JSON format
        rotation="10 MB",
        retention="30 days",
        compression="gz",
        enqueue=True,         # non-blocking (background thread)
        backtrace=True,
        diagnose=False,       # set True only in dev (can expose data in tracebacks)
    )
```

`serialize=True` produces NDJSON (newline-delimited JSON), one log entry per line. The `enqueue=True` flag makes log writes non-blocking — essential for a FastAPI async app where synchronous I/O in the hot path causes latency spikes.

### Where to Initialize loguru

Call `setup_logging()` at module import time in `app/logging_config.py`, then import this module early in `app/main.py` before any other app code:

```python
# app/main.py
from app.logging_config import setup_logging
setup_logging()  # first thing, before other imports that might log

from fastapi import FastAPI
# ... rest of imports
```

This ensures loguru is configured before any service module or Celery code imports it. The `logger` object from loguru is a global singleton — once configured, all `from loguru import logger` calls in other modules use the same sinks.

For Celery workers, add `setup_logging()` in the Celery app module so workers also use JSON logging.

### Alembic Migration Baseline

The baseline migration (created at the end of Phase 1) should include all four tables in a single revision:
1. `users` — from 01-02
2. `audit_log` — from 01-04

The pattern for generating:
```bash
alembic revision --autogenerate -m "baseline: users and audit_log"
alembic upgrade head
```

Always review autogenerated migrations before running. The `--autogenerate` output must be checked for:
- Missing ENUM type creation (`CREATE TYPE user_role AS ENUM(...)`)
- Index creation for `email`, `user_id`, `action`, `created_at`
- `ondelete="SET NULL"` foreign key constraint on `audit_log.user_id`

---

## Validation Architecture

### Test Infrastructure Setup

```python
# tests/conftest.py
import asyncio
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.main import app
from app.database import Base, get_db  # get_db is the dependency to override
from app.config import settings

# Use a separate test DB to avoid touching dev/prod data
TEST_DATABASE_URL = settings.DATABASE_URL.replace("/seo_platform", "/seo_platform_test")

@pytest_asyncio.fixture(scope="session")
async def test_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()

@pytest_asyncio.fixture
async def db_session(test_engine):
    """Per-test async session with rollback for isolation."""
    async with test_engine.begin() as conn:
        session = AsyncSession(bind=conn)
        try:
            yield session
        finally:
            await session.close()
            await conn.rollback()  # rolls back all changes for test isolation

@pytest_asyncio.fixture
async def client(db_session):
    """AsyncClient with DB dependency overridden to use test session."""
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
```

In `pyproject.toml`:
```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"  # no need to decorate every async test
```

### Test Scenarios by Plan Area

**01-01 (Stack bootstrap):**
- `test_api_health`: GET / returns 200 (smoke test for lifespan startup)
- `test_db_connection`: DB session dependency yields an active session
- Test Redis connectivity via a test endpoint or direct `redis.asyncio` ping

**01-02 (Auth endpoints):**
```python
async def test_login_success(client, db_session):
    # Create user first
    user = await create_test_user(db_session, email="test@example.com", password="secret123")
    resp = await client.post("/auth/token", data={"username": "test@example.com", "password": "secret123"})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

async def test_login_wrong_password(client, db_session):
    await create_test_user(db_session, email="test@example.com", password="correct")
    resp = await client.post("/auth/token", data={"username": "test@example.com", "password": "wrong"})
    assert resp.status_code == 401

async def test_jwt_expiry():
    """Unit test: decode an expired token should raise JWTError."""
    from jose import JWTError
    from app.auth.jwt import create_access_token, decode_access_token
    from datetime import timedelta
    # Monkeypatch expire time to -1 minute
    expired_token = create_expired_token("user-id", "admin")
    with pytest.raises(JWTError):
        decode_access_token(expired_token)

async def test_protected_endpoint_no_token(client):
    resp = await client.get("/admin/users")
    assert resp.status_code == 401

async def test_protected_endpoint_with_token(client, db_session):
    user = await create_test_user(db_session, role="admin")
    token = create_access_token(str(user.id), "admin")
    resp = await client.get("/admin/users", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
```

**01-03 (RBAC — 403 paths):**
```python
async def test_manager_cannot_access_admin_endpoint(client, db_session):
    user = await create_test_user(db_session, role="manager")
    token = create_access_token(str(user.id), "manager")
    resp = await client.post("/admin/users", json={...}, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403

async def test_client_cannot_access_user_management(client, db_session):
    user = await create_test_user(db_session, role="client")
    token = create_access_token(str(user.id), "client")
    resp = await client.get("/admin/users", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403

async def test_service_layer_role_enforcement(db_session):
    """Call service directly — bypasses HTTP layer — tests SEC-04."""
    from app.services.user_service import list_users
    from app.models.user import User, UserRole
    manager_user = User(role=UserRole.manager, ...)
    with pytest.raises(HTTPException) as exc_info:
        await list_users(db_session, current_user=manager_user)
    assert exc_info.value.status_code == 403
```

**01-04 (Audit log):**
```python
async def test_login_creates_audit_entry(client, db_session):
    user = await create_test_user(db_session, email="audit@test.com", password="pass123")
    await client.post("/auth/token", data={"username": "audit@test.com", "password": "pass123"})

    result = await db_session.execute(
        select(AuditLog).where(AuditLog.action == "user_login").order_by(AuditLog.created_at.desc())
    )
    entry = result.scalar_one_or_none()
    assert entry is not None
    assert entry.user_id == user.id

async def test_user_creation_creates_audit_entry(client, db_session):
    admin = await create_test_user(db_session, role="admin")
    token = create_access_token(str(admin.id), "admin")
    await client.post("/admin/users", json={"email": "new@test.com", ...}, headers={"Authorization": f"Bearer {token}"})

    result = await db_session.execute(select(AuditLog).where(AuditLog.action == "user_created"))
    entry = result.scalar_one_or_none()
    assert entry is not None
    assert str(entry.user_id) == str(admin.id)
```

### Docker Compose Health Check Verification

Outside of pytest, verify INFRA-01 with:
```bash
docker compose up --build -d
docker compose ps  # all services should show "healthy" or "running"
docker compose logs worker | grep -E "(crawl|wp|default)"  # verify 3 queues wired
```

In CI (if added), use `docker compose up --wait` (Compose v2.1+) which waits for health checks to pass before exiting.

### Coverage Target

Per project constraints: service layer coverage > 60% by Phase 4. Phase 1 should aim for:
- 100% of auth service functions (login, hash, verify, JWT encode/decode)
- 100% of RBAC dependency functions (role checks)
- 100% of audit log write paths
- All 403/401/404 error paths tested explicitly

Run with:
```bash
pytest --cov=app --cov-report=term-missing --cov-fail-under=60
```

---

## Cross-Cutting Concerns for All Plans

### Sync vs. Async Boundary (critical for Phase 1 foundations)

The async/sync split must be established in Phase 1 because every subsequent phase builds on it:

| Layer | Session Type | Driver |
|-------|-------------|--------|
| FastAPI routes | `AsyncSession` from `async_sessionmaker` | asyncpg |
| Celery tasks (Phase 3+) | `Session` from `sessionmaker` (sync) | psycopg2 or psycopg3-sync |

In Phase 1, Celery tasks don't access the DB. But `SYNC_DATABASE_URL` and `SyncSessionLocal` should be defined in `app/celery_db.py` now, even if unused, so Phase 3 has a ready pattern to follow.

### Security Baseline Checklist (from PITFALLS research)

Before Phase 1 is considered done:
- [ ] `.env` in `.gitignore`; `.env.example` has no real secrets
- [ ] `SECRET_KEY` generated with `openssl rand -hex 32` and documented
- [ ] `password_hash` column never returned in API responses (Pydantic response schema excludes it)
- [ ] Plaintext passwords never appear in loguru output (verify with a test login)
- [ ] `is_active=False` check in `get_current_user` dependency (deactivated users rejected)
- [ ] JWT `exp=24h` verified by test

### What Celery Beat Needs from Phase 1

Phase 1 starts Beat with `redbeat.schedulers.RedBeatScheduler`. In Phase 1, Beat has no tasks to schedule — it starts, connects to Redis, and idles. Verify in logs that Beat starts without errors. The redbeat configuration (`REDBEAT_REDIS_URL`) must be set in `celery_app.conf` to point to the same Redis. This ensures Phase 4 (crawl scheduling) can add entries to redbeat without any infra changes.

---

## RESEARCH COMPLETE
