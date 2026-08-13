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

# Start the server. Shell form (sh -c) so ${PORT}/${WEB_WORKERS} expand at
# runtime AND `&&` chains the migration before the server. The host injects
# $PORT (Render/Railway); standalone `docker run` falls back to 8000.
#
# Migrations run here on startup — `alembic upgrade head` is idempotent (a no-op
# once the DB is at head) and takes an advisory lock during a real migration, so
# it is safe on a single instance. This replaces Railway's railway.toml
# preDeployCommand, which Render's free tier does not support; a paid Render plan
# can move it to render.yaml's preDeployCommand instead. WEB_WORKERS defaults to
# 2; set it to 1 on small instances (e.g. Render free 512 MB).
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers ${WEB_WORKERS:-2}"]

