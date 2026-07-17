"""
Greena — API v1 Router
All v1 endpoint routers are registered here.
Sprint 0: Auth only.
Sprint 2: Farm infrastructure added.
Sprint 3: Flock lifecycle and operations added.
Sprint 4: Health module (vaccination records + disease alerts) added.
Sprint 5: Finance module (expenses, revenue, snapshots, calculators) added.
Sprint 6: ARIA AI module (conversations, insights, recommendations, usage) added.
Sprint 7: Platform layer (notifications, market prices) added.
Sprint 8: Admin module (platform stats, user/farm management, AI usage) added.
Sprint 11: Farm Data Export System (PDF, Excel, CSV) added.
"""

from fastapi import APIRouter

from app.api.v1.endpoints import auth, farms, flocks, health, finance, aria, feed
from app.api.v1.endpoints import finance_analytics
from app.api.v1.endpoints import notifications, market
from app.api.v1.endpoints import admin
from app.api.v1.endpoints import exports
from app.api.v1.endpoints import organizations

api_router = APIRouter()

# ── Sprint 0 ──────────────────────────────────────────────────────────────────
api_router.include_router(auth.router)

# ── Phase 2 (Organizations / workspace-first onboarding) ──────────────────────
api_router.include_router(organizations.router)

# ── Sprint 2 ─────────────────────────────────────────────────────────────────
api_router.include_router(farms.router)

# ── Sprint 3 ─────────────────────────────────────────────────────────────────
api_router.include_router(flocks.router)

# ── Sprint 4 ─────────────────────────────────────────────────────────────────
api_router.include_router(health.router)

# ── Phase 3, Module 4 (Feed Management) ───────────────────────────────────────
api_router.include_router(feed.router)

# ── Sprint 5 (Finance) ────────────────────────────────────────────────────────
api_router.include_router(finance.router)

# ── Module 5 (Finance analytics, reports, transactions, cash flow) ────────────
api_router.include_router(finance_analytics.router)

# ── Sprint 6 (ARIA) ───────────────────────────────────────────────────────────
api_router.include_router(aria.router)

# ── Sprint 7 (Platform Layer) ─────────────────────────────────────────────────
api_router.include_router(notifications.router)
api_router.include_router(market.router)

# ── Sprint 8 (Admin Module) ───────────────────────────────────────────────────
api_router.include_router(admin.router)

# ── Sprint 11 (Farm Data Export) ─────────────────────────────────────────────
api_router.include_router(exports.router)
