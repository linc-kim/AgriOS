#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# AGRIOS — Database Migration Helper
# ─────────────────────────────────────────────────────────────────────────────

set -e

cd "$(dirname "$0")/../backend"
source .venv/bin/activate

COMMAND="${1:-up}"

case "$COMMAND" in
  up)
    echo "Running migrations..."
    alembic upgrade head
    echo "✓ All migrations applied"
    ;;
  down)
    echo "Rolling back last migration..."
    alembic downgrade -1
    echo "✓ Rolled back"
    ;;
  status)
    alembic current
    ;;
  history)
    alembic history --verbose
    ;;
  new)
    if [ -z "$2" ]; then
      echo "Usage: ./scripts/migrate.sh new <description>"
      exit 1
    fi
    alembic revision --autogenerate -m "$2"
    echo "✓ New migration created"
    ;;
  *)
    echo "Usage: ./scripts/migrate.sh [up|down|status|history|new <description>]"
    exit 1
    ;;
esac
