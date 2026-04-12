"""Standalone async DB session factory for the bot.

Does NOT import app.database or app.main to avoid pulling in FastAPI
startup logic (lifespan, middleware, routers) into the bot container.
Uses the same PostgreSQL connection string as the main app.
"""
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from bot.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=5,
    max_overflow=2,
    pool_timeout=30,
    pool_pre_ping=True,
    echo=False,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)
