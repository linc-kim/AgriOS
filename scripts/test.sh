#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# AGRIOS — Test Runner
# ─────────────────────────────────────────────────────────────────────────────

set -e

TARGET="${1:-all}"

run_backend_tests() {
  echo "Running backend tests..."
  cd "$(dirname "$0")/../backend"
  source .venv/bin/activate
  pytest "$@" -v
  deactivate
}

run_frontend_tests() {
  echo "Running frontend tests..."
  cd "$(dirname "$0")/../frontend"
  npm test -- --run
}

case "$TARGET" in
  backend)
    run_backend_tests "${@:2}"
    ;;
  frontend)
    run_frontend_tests
    ;;
  all)
    run_backend_tests
    run_frontend_tests
    ;;
  *)
    echo "Usage: ./scripts/test.sh [all|backend|frontend]"
    exit 1
    ;;
esac

echo "✓ All tests passed"
