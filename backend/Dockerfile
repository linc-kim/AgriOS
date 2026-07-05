# ─────────────────────────────────────────────────────────────────────────────
# AGRIOS Backend — Production Dockerfile
# Python 3.12-slim for minimal image size
# ─────────────────────────────────────────────────────────────────────────────

FROM python:3.12-slim AS base

# Prevent Python from writing .pyc files and buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TZ=Africa/Nairobi

WORKDIR /app

# ── System Dependencies ───────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# ── Python Dependencies ───────────────────────────────────────────────────────
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# ── Application Code ──────────────────────────────────────────────────────────
COPY . .

# ── Non-root User ─────────────────────────────────────────────────────────────
RUN adduser --disabled-password --gecos "" agrios
USER agrios

# ── Startup ───────────────────────────────────────────────────────────────────
EXPOSE 8000

# Start the server. Shell form (sh -c) so ${PORT} is expanded at runtime — this
# is the single start command Railway uses (railway.toml sets no startCommand,
# because a toml startCommand runs without a shell and would pass "$PORT"
# literally). Railway injects $PORT; local/standalone `docker run` falls back to
# 8000. Migrations run via railway.toml's preDeployCommand on Railway; for a
# standalone container run `alembic upgrade head` first (see DEPLOYMENT.md).
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 2"]

