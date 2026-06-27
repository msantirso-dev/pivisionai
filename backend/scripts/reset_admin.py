"""Reset admin password to default (admin / admin123)."""

import asyncio
import logging
import sys

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    from app.services.db_bootstrap import ensure_database_ready, reset_admin_password

    password = sys.argv[1] if len(sys.argv) > 1 else "admin123"
    await ensure_database_ready(create_admin=False)
    await reset_admin_password(password)
    print(f"OK: usuario admin restablecido (password: {password})")


if __name__ == "__main__":
    asyncio.run(main())
