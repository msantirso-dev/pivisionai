#!/bin/sh
set -e
cd /app
export PYTHONPATH=/app
python scripts/init_db.py || echo "init_db: skipped or already initialized"
exec "$@"
