#!/bin/sh
set -e
cd /app
export PYTHONPATH=/app

echo "Esperando PostgreSQL..."
python - <<'PY'
import asyncio
from app.services.db_bootstrap import ensure_database_ready

async def main():
    await ensure_database_ready(create_admin=True)

asyncio.run(main())
PY

exec "$@"
