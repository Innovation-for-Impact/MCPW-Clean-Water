"""Seed initial users for development/testing."""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select  # noqa: E402

from src.models.database import async_session_factory, engine  # noqa: E402
from src.models.user import User  # noqa: E402
from src.services.auth import hash_password  # noqa: E402

SEED_USERS = [
    {"username": "admin", "password": "admin123", "role": "admin"},
    {"username": "responder", "password": "responder123", "role": "responder"},
    {"username": "viewer", "password": "viewer123", "role": "viewer"},
]


async def main():
    async with async_session_factory() as session:
        for u in SEED_USERS:
            existing = await session.execute(
                select(User).where(User.username == u["username"])
            )
            if existing.scalar_one_or_none():
                print(f"User '{u['username']}' already exists, skipping")
                continue
            user = User(
                username=u["username"],
                password_hash=hash_password(u["password"]),
                role=u["role"],
            )
            session.add(user)
            print(f"Created user '{u['username']}' with role '{u['role']}'")
        await session.commit()

    await engine.dispose()


asyncio.run(main())
