#!/bin/sh
set -e

alembic upgrade head

python /app/src/envoy/server/init_db.py