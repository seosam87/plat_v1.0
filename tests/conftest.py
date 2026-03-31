import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
)

from app.database import Base
from app.dependencies import get_db
from app.main import app

try:
    from app.config import settings
    TEST_DATABASE_URL = settings.DATABASE_URL.replace(
        f"/{settings.DATABASE_URL.split('/')[-1]}",
        "/seo_platform_test",
    )
except Exception:
    TEST_DATABASE_URL = "postgresql+asyncpg://seo_user:changeme@postgres:5432/seo_platform_test"


@pytest_asyncio.fixture
async def db_session():
    """Per-test async session with SAVEPOINT isolation and full rollback after."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as setup_conn:
        await setup_conn.run_sync(Base.metadata.create_all, checkfirst=True)

    conn = await engine.connect()
    trans = await conn.begin()
    session = AsyncSession(
        bind=conn,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    try:
        yield session
    finally:
        await session.close()
        await trans.rollback()
        await conn.close()
        await engine.dispose()


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
