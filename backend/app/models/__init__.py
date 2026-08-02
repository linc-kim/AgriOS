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
from app.models.automation import AutomationRule, Reminder
from app.models.ai_platform import AIResponseCache
from app.models.admin_platform import BackgroundJob, FeatureFlag, SystemConfig
from app.models.production import (
    Backup,
    ExportJob,
    ImportJob,
    ReleaseRecord,
    RestoreRun,
)
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
from app.models.ai_assistant import AIDocument, AISettings
from app.models.mission import Mission, MissionRevision
from app.models.aviculture import (
    AviAviary,
    AviAviaryEvent,
    AviAviaryFixture,
    AviAviaryMedia,
    AviAviaryTask,
    AviAviaryZone,
    AviBird,
    AviBirdDocument,
    AviBirdEvent,
    AviBirdMedia,
    AviBirdMutation,
    AviBirdOwnership,
    AviBreed,
    AviBreedingGoal,
    AviBreedingProgram,
    AviCandlingRecord,
    AviClutch,
    AviDiseaseEvent,
    AviEgg,
    AviEnvironmentalReading,
    AviHatchEvent,
    AviHealthRecord,
    AviIncubationBatch,
    AviIncubationLog,
    AviMutation,
    AviQuarantine,
    AviPair,
    AviPairEvent,
    AviSpecies,
    AviValuation,
    AviWorkflow,
    AviWorkflowEvent,
)
from app.models.bsf import (
    BsfBatch,
    BsfBatchDocument,
    BsfBatchEvent,
    BsfBatchMedia,
    BsfColony,
    BsfEnvironmentalReading,
    BsfFeedingEvent,
    BsfFeedstockLot,
    BsfFrassProduction,
    BsfHarvestEvent,
    BsfLifecycleEvent,
    BsfMortalityEvent,
    BsfProductionUnit,
    BsfSpecies,
)
from app.models.rabbit import (
    Rabbit,
    RabbitBloodline,
    RabbitBreed,
    RabbitBreeding,
    RabbitBuilding,
    RabbitCage,
    RabbitDocument,
    RabbitEvent,
    RabbitFeedRecord,
    RabbitHealthRecord,
    RabbitLitter,
    RabbitMedia,
    RabbitMortality,
    RabbitSale,
    RabbitVaccination,
    RabbitWeight,
    RabbitRabbitry,
    RabbitRoom,
    RabbitRow,
)
from app.models.small_ruminant import (
    SmallRuminant,
    SmallRuminantBirth,
    SmallRuminantBloodline,
    SmallRuminantBreed,
    SmallRuminantBreeding,
    SmallRuminantDocument,
    SmallRuminantEvent,
    SmallRuminantGroup,
    SmallRuminantHerd,
    SmallRuminantDeworming,
    SmallRuminantFeedRecord,
    SmallRuminantFleece,
    SmallRuminantHealthRecord,
    SmallRuminantHoofCare,
    SmallRuminantLactation,
    SmallRuminantMedia,
    SmallRuminantMilkRecord,
    SmallRuminantMortality,
    SmallRuminantPasture,
    SmallRuminantPen,
    SmallRuminantSale,
    SmallRuminantShearing,
    SmallRuminantVaccination,
    SmallRuminantWeight,
)
from app.models.swine import (
    SwineBloodline,
    SwineBreed,
    SwineDocument,
    SwineEvent,
    SwineGroup,
    SwineHerd,
    SwineMedia,
    SwinePen,
    SwinePig,
)
from app.models.growth import (
    GrowthGoal,
    GrowthMilestone,
    GrowthPlan,
    GrowthPlanRevision,
)
from app.models.ops_planner import (
    OpsAssignment,
    OpsChecklist,
    OpsChecklistItem,
    OpsCompletion,
    OpsException,
    OpsManual,
    OpsManualRevision,
    OpsRecommendation,
    OpsRoutine,
    OpsRoutineTemplate,
    OpsRoutineVersion,
    OpsSchedule,
    OpsShift,
    OpsSOP,
    OpsTaskTemplate,
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
    # Automation (Migration 046)
    "AutomationRule",
    "Reminder",
    # AI Platform (Migration 047)
    "AIResponseCache",
    # Admin Platform (Migration 048)
    "FeatureFlag",
    "SystemConfig",
    "BackgroundJob",
    # Production Readiness (Migration 050)
    "Backup",
    "RestoreRun",
    "ImportJob",
    "ExportJob",
    "ReleaseRecord",
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
    # AI Assistant (Module 13 Part 8)
    "AISettings",
    "AIDocument",
    # Mission Control (Module 14)
    "Mission",
    "MissionRevision",
    # Aviculture (Module 15, Migration 053)
    "AviSpecies",
    "AviBreed",
    "AviMutation",
    "AviAviary",
    "AviBird",
    "AviBirdMutation",
    "AviPair",
    "AviBirdMedia",
    "AviBirdDocument",
    "AviHealthRecord",
    # Aviculture Collection Management (Module 15 Part 2, Migration 054)
    "AviBirdOwnership",
    "AviBirdEvent",
    # Aviculture Aviary Management (Module 15 Part 3, Migration 055)
    "AviAviaryZone",
    "AviAviaryFixture",
    "AviEnvironmentalReading",
    "AviAviaryTask",
    "AviAviaryEvent",
    "AviAviaryMedia",
    # Aviculture Breeding Engine (Module 15 Part 4, Migration 056)
    "AviBreedingProgram",
    "AviBreedingGoal",
    "AviPairEvent",
    # Aviculture Incubation Engine (Module 15 Part 5, Migration 057)
    "AviClutch",
    "AviIncubationBatch",
    "AviEgg",
    "AviIncubationLog",
    "AviCandlingRecord",
    "AviHatchEvent",
    # Aviculture Health Engine (Module 15 Part 6, Migration 058)
    "AviQuarantine",
    "AviDiseaseEvent",
    # Aviculture Valuation (Module 15 Part 7, Migration 059)
    "AviValuation",
    # Aviculture Workflows (Module 15 Part 9, Migration 060)
    "AviWorkflow",
    "AviWorkflowEvent",
    # Black Soldier Fly (Module 16 Part 1, Migration 061)
    "BsfSpecies",
    "BsfProductionUnit",
    "BsfColony",
    "BsfBatch",
    "BsfLifecycleEvent",
    "BsfBatchEvent",
    "BsfBatchMedia",
    "BsfBatchDocument",
    "BsfFeedstockLot",
    "BsfFeedingEvent",
    "BsfEnvironmentalReading",
    "BsfHarvestEvent",
    "BsfFrassProduction",
    "BsfMortalityEvent",
    # Rabbit Management (Module 17 Part 1, Migration 066)
    "RabbitBreed",
    "RabbitBloodline",
    "RabbitRabbitry",
    "RabbitBuilding",
    "RabbitRoom",
    "RabbitRow",
    "RabbitCage",
    "Rabbit",
    "RabbitEvent",
    "RabbitMedia",
    "RabbitDocument",
    # Rabbit Breeding & Litters (Module 17 Milestone 3, Migration 067)
    "RabbitBreeding",
    "RabbitLitter",
    # Rabbit Growth, Weight & Feed (Module 17 Milestone 4, Migration 068)
    "RabbitWeight",
    "RabbitFeedRecord",
    # Rabbit Health, Vaccination & Mortality (Module 17 Milestone 5, Migration 069)
    "RabbitHealthRecord",
    "RabbitVaccination",
    "RabbitMortality",
    # Rabbit Sales (Module 17 Milestone 6, Migration 070)
    "RabbitSale",
    # Small Ruminant — Goat + Sheep (Modules 18/19, Milestone 1, Migration 072)
    "SmallRuminantBreed",
    "SmallRuminantBloodline",
    "SmallRuminantHerd",
    "SmallRuminantGroup",
    "SmallRuminantPen",
    "SmallRuminantPasture",
    "SmallRuminant",
    "SmallRuminantEvent",
    "SmallRuminantMedia",
    "SmallRuminantDocument",
    # Small Ruminant Breeding & Birth (Milestone 3, Migration 073)
    "SmallRuminantBreeding",
    "SmallRuminantBirth",
    # Small Ruminant Growth & Feed (Milestone 4, Migration 074)
    "SmallRuminantWeight",
    "SmallRuminantFeedRecord",
    # Small Ruminant Health (Milestone 5, Migration 075)
    "SmallRuminantHealthRecord",
    "SmallRuminantVaccination",
    "SmallRuminantDeworming",
    "SmallRuminantHoofCare",
    "SmallRuminantMortality",
    # Small Ruminant Dairy — goat milk/lactation (Milestone 6, Migration 076)
    "SmallRuminantLactation",
    "SmallRuminantMilkRecord",
    # Small Ruminant Wool — sheep shearing/fleece (Milestone 7, Migration 077)
    "SmallRuminantShearing",
    "SmallRuminantFleece",
    # Small Ruminant Sales (Milestone 8, Migration 078)
    "SmallRuminantSale",
    # Swine — Pig Framework (Module 20, Milestone 1, Migration 079)
    "SwineBreed",
    "SwineBloodline",
    "SwineHerd",
    "SwineGroup",
    "SwinePen",
    "SwinePig",
    "SwineEvent",
    "SwineMedia",
    "SwineDocument",
    # Growth Planner (Platform, Migration 065)
    "GrowthPlan",
    "GrowthGoal",
    "GrowthMilestone",
    "GrowthPlanRevision",
    # Operations Planner (Platform Module 5, Migration 071)
    "OpsManual",
    "OpsManualRevision",
    "OpsRoutineTemplate",
    "OpsShift",
    "OpsSOP",
    "OpsRoutine",
    "OpsRoutineVersion",
    "OpsSchedule",
    "OpsTaskTemplate",
    "OpsChecklist",
    "OpsChecklistItem",
    "OpsAssignment",
    "OpsCompletion",
    "OpsException",
    "OpsRecommendation",
    # Platform Layer (Migrations 028-030)
    "Notification",
    "AuditLog",
    "MarketPrice",
]
