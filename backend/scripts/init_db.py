"""Database initialization and seed data."""

import asyncio
import logging

from app.services.db_bootstrap import ensure_database_ready

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def init_db():
    await ensure_database_ready(create_admin=True)


if __name__ == "__main__":
    asyncio.run(init_db())
