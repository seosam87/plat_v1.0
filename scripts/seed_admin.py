"""Seed script: create default admin user if none exists.
Usage: docker compose exec api python scripts/seed_admin.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy import select
from app.database import AsyncSessionLocal, engine
from app.models.user import User, UserRole
from app.auth.password import hash_password


async def seed() -> None:
    async with AsyncSessionLocal() as db:
        existing = await db.execute(
            select(User).where(User.role == UserRole.admin)
        )
        if existing.scalar_one_or_none():
            print("Admin already exists — skipping seed.")
            return

        admin = User(
            username="admin",
            email="admin@example.com",
            password_hash=hash_password("changeme"),
            role=UserRole.admin,
            is_active=True,
        )
        db.add(admin)
        await db.commit()
        print("Created admin user: admin@example.com / changeme")


if __name__ == "__main__":
    asyncio.run(seed())
