"""Database initialization and seed data."""

import asyncio
import logging

from sqlalchemy import select

from app.config import get_settings
from app.core.security import get_password_hash
from app.database import AsyncSessionLocal, engine
from app.models import Base, Role, User, UserRole

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
settings = get_settings()


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created")

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.username == "admin"))
        if result.scalar_one_or_none():
            logger.info("Admin user already exists")
            return

        admin = User(
            email="admin@pivision.local",
            username="admin",
            hashed_password=get_password_hash("admin123"),
            full_name="Administrador",
            role=UserRole.ADMIN,
        )
        session.add(admin)

        roles = [
            Role(name="admin", permissions={"all": True}, description="Administrador total"),
            Role(name="supervisor", permissions={"cameras": True, "rules": True, "events": True}, description="Supervisor"),
            Role(name="operator", permissions={"events": True, "view": True}, description="Operador"),
            Role(name="readonly", permissions={"view": True}, description="Solo lectura"),
        ]
        for role in roles:
            session.add(role)

        await session.commit()
        logger.info("Default admin user created: admin / admin123")


if __name__ == "__main__":
    asyncio.run(init_db())
