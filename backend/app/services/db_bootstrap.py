"""Database bootstrap: wait for Postgres, create schema and default admin."""

import asyncio
import logging

from sqlalchemy import select, text

from app.core.security import get_password_hash
from app.database import AsyncSessionLocal, engine
from app.models import Base, Role, User, UserRole

logger = logging.getLogger(__name__)

DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "admin123"


async def wait_for_database(max_attempts: int = 30, delay_seconds: float = 2.0) -> bool:
    for attempt in range(1, max_attempts + 1):
        try:
            async with engine.begin() as conn:
                await conn.execute(text("SELECT 1"))
            logger.info("Database connection OK (attempt %s)", attempt)
            return True
        except Exception as exc:
            logger.warning("Database not ready (attempt %s/%s): %s", attempt, max_attempts, exc)
            if attempt < max_attempts:
                await asyncio.sleep(delay_seconds)
    return False


async def ensure_database_ready(create_admin: bool = True) -> None:
    if not await wait_for_database():
        raise RuntimeError("Database unavailable after retries")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(
            text("ALTER TABLE detection_rules ADD COLUMN IF NOT EXISTS context_description TEXT")
        )
        await conn.execute(
            text(
                "ALTER TABLE cameras ADD COLUMN IF NOT EXISTS connection_mode VARCHAR(20) DEFAULT 'local'"
            )
        )
        await conn.execute(
            text("ALTER TABLE cameras ADD COLUMN IF NOT EXISTS device_serial VARCHAR(64)")
        )
        await conn.execute(text("ALTER TABLE cameras ALTER COLUMN ip_address DROP NOT NULL"))

    if not create_admin:
        return

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.username == DEFAULT_ADMIN_USERNAME))
        if result.scalar_one_or_none():
            logger.info("Admin user already exists")
            return

        session.add(
            User(
                email="admin@pivision.local",
                username=DEFAULT_ADMIN_USERNAME,
                hashed_password=get_password_hash(DEFAULT_ADMIN_PASSWORD),
                full_name="Administrador",
                role=UserRole.ADMIN,
            )
        )

        roles = [
            Role(name="admin", permissions={"all": True}, description="Administrador total"),
            Role(name="supervisor", permissions={"cameras": True, "rules": True, "events": True}, description="Supervisor"),
            Role(name="operator", permissions={"events": True, "view": True}, description="Operador"),
            Role(name="readonly", permissions={"view": True}, description="Solo lectura"),
        ]
        for role in roles:
            existing = await session.execute(select(Role).where(Role.name == role.name))
            if not existing.scalar_one_or_none():
                session.add(role)

        await session.commit()
        logger.info("Default admin user created: %s / %s", DEFAULT_ADMIN_USERNAME, DEFAULT_ADMIN_PASSWORD)


async def reset_admin_password(password: str = DEFAULT_ADMIN_PASSWORD) -> None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.username == DEFAULT_ADMIN_USERNAME))
        user = result.scalar_one_or_none()
        if user:
            user.hashed_password = get_password_hash(password)
            user.is_active = True
        else:
            session.add(
                User(
                    email="admin@pivision.local",
                    username=DEFAULT_ADMIN_USERNAME,
                    hashed_password=get_password_hash(password),
                    full_name="Administrador",
                    role=UserRole.ADMIN,
                )
            )
        await session.commit()
        logger.info("Admin password reset for user: %s", DEFAULT_ADMIN_USERNAME)
