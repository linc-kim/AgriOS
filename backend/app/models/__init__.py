"""
Greena Models — Public exports
Import all models here so Alembic can discover them for autogenerate.
"""

from app.models.base import AGRIOSBase
from app.models.auth import (
    EmailToken,
    IdentityProvider,
    OTPRequest,
    Role,
    Session,
    User,
    UserRole,
)
from app.models.farm import (
    Farm,
    FarmMember,
    FarmUnit,
    ProductionHouse,
    SpeciesProfile,
    SubscriptionPlan,
)
from app.models.organization import Organization, OrganizationMember
from app.models.flock import (
    DailyLog,
    FeedPurchase,
    Flock,
    ProductionRecord,
    WeighinRecord,
)
from app.models.health import DiseaseAlert, HealthEvent, VaccinationRecord
from app.models.feed import (
    FeedInventoryItem,
    FeedSupplier,
    FeedTransaction,
)
from app.models.inventory import (
    Asset,
    AssetMaintenance,
    InventoryItem,
    InventoryMovement,
    InventorySupplier,
)
from app.models.reporting import SavedReport
from app.models.finance import (
    ExpenseCategory,
    Expense,
    RevenueRecord,
    FinancialSnapshot,
)
from app.models.ai import (
    AIConversation,
    AIMessage,
    AIInsight,
    AIRecommendation,
    AIUsageLog,
)
from app.models.platform import (
    Notification,
    AuditLog,
    MarketPrice,
)

__all__ = [
    # Base
    "AGRIOSBase",
    # Auth (Migrations 001-005)
    "Role",
    "User",
    "UserRole",
    "OTPRequest",
    "Session",
    "IdentityProvider",
    "EmailToken",
    # Farm Infrastructure (Migrations 006-011)
    "SubscriptionPlan",
    "SpeciesProfile",
    "Farm",
    "FarmMember",
    "FarmUnit",
    "ProductionHouse",
    "Organization",
    "OrganizationMember",
    # Flock Operations (Migrations 012-016)
    "Flock",
    "DailyLog",
    "ProductionRecord",
    "WeighinRecord",
    "FeedPurchase",
    # Health (Migrations 017-018)
    "VaccinationRecord",
    "DiseaseAlert",
    "HealthEvent",
    # Feed Management (Migration 041)
    "FeedSupplier",
    "FeedInventoryItem",
    "FeedTransaction",
    # Inventory & Assets (Migration 044)
    "InventorySupplier",
    "InventoryItem",
    "InventoryMovement",
    "Asset",
    "AssetMaintenance",
    # Reporting (Migration 045)
    "SavedReport",
    # Finance (Migrations 019-022)
    "ExpenseCategory",
    "Expense",
    "RevenueRecord",
    "FinancialSnapshot",
    # AI / ARIA (Migrations 023-027)
    "AIConversation",
    "AIMessage",
    "AIInsight",
    "AIRecommendation",
    "AIUsageLog",
    # Platform Layer (Migrations 028-030)
    "Notification",
    "AuditLog",
    "MarketPrice",
]
