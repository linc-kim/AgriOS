#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# AGRIOS — Local Development Setup
# Run once after cloning the repository.
# ─────────────────────────────────────────────────────────────────────────────

set -e

echo ""
echo "🌱 AGRIOS Local Setup"
echo "─────────────────────"

# ── Prerequisites Check ───────────────────────────────────────────────────────

check_command() {
  if ! command -v "$1" &>/dev/null; then
    echo "❌ $1 is not installed. Please install it first."
    exit 1
  fi
}

echo "Checking prerequisites..."
check_command python3
check_command node
check_command npm
check_command docker

echo "✓ All prerequisites found"
echo ""

# ── Backend Setup ─────────────────────────────────────────────────────────────

echo "Setting up backend..."
cd backend

if [ ! -f ".env" ]; then
  cp .env.example .env
  echo "✓ Created backend/.env from .env.example"
  echo "  ⚠️  Edit backend/.env with your API keys before running"
fi

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
echo "✓ Backend Python environment ready"
deactivate

cd ..

# ── Frontend Setup ────────────────────────────────────────────────────────────

echo "Setting up frontend..."
cd frontend

if [ ! -f ".env" ]; then
  cp .env.example .env
  echo "✓ Created frontend/.env from .env.example"
fi

npm install
echo "✓ Frontend Node modules installed"

cd ..

# ── Database ──────────────────────────────────────────────────────────────────

echo "Starting database..."
docker compose -f infrastructure/docker-compose.yml up -d db db_test
echo "✓ PostgreSQL running on port 5432 (dev) and 5433 (test)"

# Wait for DB to be ready
echo "Waiting for database..."
sleep 3

# Run migrations
echo "Running migrations..."
cd backend
source .venv/bin/activate
alembic upgrade head
echo "✓ Migrations 001–005 applied"
deactivate
cd ..

echo ""
echo "✅ AGRIOS is ready!"
echo ""
echo "Start the backend:  cd backend && source .venv/bin/activate && uvicorn app.main:app --reload"
echo "Start the frontend: cd frontend && npm run dev"
echo "API docs:           http://localhost:8000/docs"
echo "PWA:                http://localhost:5173"
echo ""
