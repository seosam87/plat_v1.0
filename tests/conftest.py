from uuid import UUID

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
from app.models.user import User

# Re-export the smoke seed fixture so it's discoverable from the top-level
# conftest without test modules needing to import it directly.
from tests.fixtures.smoke_seed import smoke_seed, SMOKE_IDS  # noqa: F401

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


@pytest_asyncio.fixture(scope="session")
async def smoke_client(smoke_seed):
    """Session-scoped AsyncClient for the UI smoke crawler (Phase 15.1).

    Auth is bypassed via ``app.dependency_overrides`` on ``get_current_user``
    and ``require_admin`` — the crawler MUST NOT POST to /ui/login.

    Per CONTEXT D-01 + RESEARCH "Critical detail" SAVEPOINT strategy:
    ``get_db`` is overridden to yield a FRESH AsyncSession per request bound
    to the seed's outer connection with ``join_transaction_mode="create_savepoint"``,
    so each request's internal commit/rollback is scoped to its own savepoint
    and the outer seed transaction stays alive for the whole session.

    Teardown explicitly pops the three overrides (no ``clear()``) so other
    test modules are unaffected.
    """
    from app.auth.dependencies import (
        get_current_user,
        require_admin,
        require_any_authenticated,
    )

    user = await smoke_seed.session.get(User, UUID(SMOKE_IDS["user_id"]))

    RequestSession = async_sessionmaker(
        bind=smoke_seed.connection,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
        class_=AsyncSession,
    )

    async def _override_db():
        async with RequestSession() as s:
            yield s

    def _override_user():
        return user

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = _override_user
    app.dependency_overrides[require_admin] = _override_user
    app.dependency_overrides[require_any_authenticated] = _override_user
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            yield ac
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(require_admin, None)
        app.dependency_overrides.pop(require_any_authenticated, None)
