"""
AGRIOS — API v1 Router
All v1 endpoint routers are registered here.
Sprint 0: Auth only.
Sprint 2: Farm infrastructure added.
Sprint 3: Flock lifecycle and operations added.
Sprint 4: Health module (vaccination records + disease alerts) added.
Sprint 5: Finance module (expenses, revenue, snapshots, calculators) added.
Sprint 6: ARIA AI module (conversations, insights, recommendations, usage) added.
Sprint 7: Platform layer (notifications, market prices) added.
Sprint 8: Admin module (platform stats, user/farm management, AI usage) added.
"""

from fastapi import APIRouter

from app.api.v1.endpoints import auth, farms, flocks, health, finance, aria
from app.api.v1.endpoints import notifications, market
from app.api.v1.endpoints import admin

api_router = APIRouter()

# ── Sprint 0 ──────────────────────────────────────────────────────────────────
api_router.include_router(auth.router)

# ── Sprint 2 ─────────────────────────────────────────────────────────────────
api_router.include_router(farms.router)

# ── Sprint 3 ─────────────────────────────────────────────────────────────────
api_router.include_router(flocks.router)

# ── Sprint 4 ─────────────────────────────────────────────────────────────────
api_router.include_router(health.router)

# ── Sprint 5 (Finance) ────────────────────────────────────────────────────────
api_router.include_router(finance.router)

# ── Sprint 6 (ARIA) ───────────────────────────────────────────────────────────
api_router.include_router(aria.router)

# ── Sprint 7 (Platform Layer) ─────────────────────────────────────────────────
api_router.include_router(notifications.router)
api_router.include_router(market.router)

# ── Sprint 8 (Admin Module) ───────────────────────────────────────────────────
api_router.include_router(admin.router)
