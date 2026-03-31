import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.database import Base
from app.dependencies import get_db
from app.main import app

# Derive test DB URL from main DB URL (replace db name)
# Falls back gracefully if DATABASE_URL is not set during collection
try:
    from app.config import settings
    TEST_DATABASE_URL = settings.DATABASE_URL.replace(
        f"/{settings.DATABASE_URL.split('/')[-1]}",
        "/seo_platform_test",
    )
except Exception:
    TEST_DATABASE_URL = "postgresql+asyncpg://seo_user:changeme@postgres:5432/seo_platform_test"


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
            await conn.rollback()


@pytest_asyncio.fixture
async def client(db_session):
    """AsyncClient with DB dependency overridden to use the test session."""
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
    app.dependency_overrides.clear()
