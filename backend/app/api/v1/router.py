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
from app.api.v1.endpoints import inventory
from app.api.v1.endpoints import reporting
from app.api.v1.endpoints import automation
from app.api.v1.endpoints import ai_platform
from app.api.v1.endpoints import notifications, market
from app.api.v1.endpoints import admin
from app.api.v1.endpoints import admin_platform
from app.api.v1.endpoints import exports
from app.api.v1.endpoints import organizations
from app.api.v1.endpoints import production
from app.api.v1.endpoints import operations
from app.api.v1.endpoints import ai_assistant
from app.api.v1.endpoints import mission
from app.api.v1.endpoints import aviculture
from app.api.v1.endpoints import aviculture_aviary
from app.api.v1.endpoints import aviculture_breeding
from app.api.v1.endpoints import aviculture_incubation
from app.api.v1.endpoints import aviculture_health
from app.api.v1.endpoints import aviculture_finance
from app.api.v1.endpoints import aviculture_reports
from app.api.v1.endpoints import aviculture_automation
from app.api.v1.endpoints import aviculture_aria
from app.api.v1.endpoints import bsf
from app.api.v1.endpoints import bsf_feeding
from app.api.v1.endpoints import bsf_environment
from app.api.v1.endpoints import bsf_harvest
from app.api.v1.endpoints import bsf_health
from app.api.v1.endpoints import bsf_finance
from app.api.v1.endpoints import bsf_reports
from app.api.v1.endpoints import bsf_growth
from app.api.v1.endpoints import bsf_aria
from app.api.v1.endpoints import rabbit
from app.api.v1.endpoints import rabbit_housing
from app.api.v1.endpoints import rabbit_breeding
from app.api.v1.endpoints import rabbit_growth
from app.api.v1.endpoints import rabbit_health
from app.api.v1.endpoints import rabbit_finance
from app.api.v1.endpoints import rabbit_reports
from app.api.v1.endpoints import rabbit_growth_planner
from app.api.v1.endpoints import rabbit_aria
from app.api.v1.endpoints import ops_planner
from app.api.v1.endpoints import sr_animals
from app.api.v1.endpoints import sr_housing
from app.api.v1.endpoints import sr_breeding
from app.api.v1.endpoints import sr_growth
from app.api.v1.endpoints import sr_health
from app.api.v1.endpoints import sr_dairy
from app.api.v1.endpoints import sr_wool
from app.api.v1.endpoints import sr_finance
from app.api.v1.endpoints import sr_reports
from app.api.v1.endpoints import sr_growth_planner
from app.api.v1.endpoints import sr_aria

from app.api.v1.endpoints import swine_animals
from app.api.v1.endpoints import swine_housing

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

# ── Module 6 (Inventory & Asset Management) ───────────────────────────────────
api_router.include_router(inventory.router)

# ── Module 7 (Reporting & Business Intelligence) ──────────────────────────────
api_router.include_router(reporting.router)

# ── Module 8 (Automation & Notifications) ─────────────────────────────────────
api_router.include_router(automation.router)

# ── Module 9 (ARIA AI Platform — predictions, forecasts, offline assistant) ───
api_router.include_router(ai_platform.router)

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

# ── Module 10 (Admin Platform) ────────────────────────────────────────────────
api_router.include_router(admin_platform.router)

# ── Sprint 11 (Farm Data Export) ─────────────────────────────────────────────
api_router.include_router(exports.router)

# ── Module 11 (Production Readiness — backups, imports, diagnostics, release) ─
api_router.include_router(production.router)

# ── Module 13 Part 7 (ARIA Operations Director — organization-scale operations) ─
api_router.include_router(operations.router)

# ── Module 13 Part 8 (ARIA AI Farm Assistant — router, multimodal, settings) ──
api_router.include_router(ai_assistant.router)

# ── Module 14 (Mission Control — the strategic operating system) ──────────────
api_router.include_router(mission.router)

# ── Module 15 (Aviculture — ornamental & specialty birds) ─────────────────────
api_router.include_router(aviculture.router)
api_router.include_router(aviculture_aviary.router)
api_router.include_router(aviculture_breeding.router)
api_router.include_router(aviculture_incubation.router)
api_router.include_router(aviculture_health.router)
api_router.include_router(aviculture_finance.router)
api_router.include_router(aviculture_reports.router)
api_router.include_router(aviculture_automation.router)
api_router.include_router(aviculture_aria.router)

# ── Module 16 (Black Soldier Fly — insect farming) ────────────────────────────
api_router.include_router(bsf.router)
api_router.include_router(bsf_feeding.router)
api_router.include_router(bsf_environment.router)
api_router.include_router(bsf_harvest.router)
api_router.include_router(bsf_health.router)
api_router.include_router(bsf_finance.router)
api_router.include_router(bsf_reports.router)
api_router.include_router(bsf_growth.router)
api_router.include_router(bsf_aria.router)

# ── Module 17 (Rabbit Management) ─────────────────────────────────────────────
api_router.include_router(rabbit.router)
api_router.include_router(rabbit_housing.router)
api_router.include_router(rabbit_breeding.router)
api_router.include_router(rabbit_growth.router)
api_router.include_router(rabbit_health.router)
api_router.include_router(rabbit_finance.router)
api_router.include_router(rabbit_reports.router)
api_router.include_router(rabbit_growth_planner.router)
api_router.include_router(rabbit_aria.router)
# Operations Planner (Platform Module 5) — cross-module recurring-operations engine
api_router.include_router(ops_planner.router)
# ── Modules 18/19 (Small Ruminant — Goat + Sheep) ─────────────────────────────
api_router.include_router(sr_animals.router)
api_router.include_router(sr_housing.router)
api_router.include_router(sr_breeding.router)
api_router.include_router(sr_growth.router)
api_router.include_router(sr_health.router)
api_router.include_router(sr_dairy.router)
api_router.include_router(sr_wool.router)
api_router.include_router(sr_finance.router)
api_router.include_router(sr_reports.router)
api_router.include_router(sr_growth_planner.router)
api_router.include_router(sr_aria.router)

api_router.include_router(swine_animals.router)
api_router.include_router(swine_housing.router)
