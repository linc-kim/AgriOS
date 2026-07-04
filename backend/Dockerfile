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

# Self-contained default for plain `docker run` (local / non-Railway): apply
# migrations, then start the server. Shell form so ${PORT} is honoured and the
# migration step can precede the server. On Railway this CMD is overridden by
# railway.toml's preDeployCommand (migrations) + startCommand (server), so
# migrations are not run twice there.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 2"]

