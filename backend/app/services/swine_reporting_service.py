"""
Greena — Swine Reporting & Analytics Service (Module 20, Milestone 9)

A pure COMPOSITION layer. It never recreates a business calculation — each domain
service owns its own math (registry, breeding, pregnancy, farrowing, feed, health,
growth, finance) and this module combines their outputs into multi-level,
explainable reports (pig / litter / pen / farm / organization) plus CSV exports.

Design guarantees:
  * Read-only — it consumes data, never mutates.
  * Nothing is stored — reports are generated dynamically from the engines on demand
    (no dashboard/KPI tables). Caching, if ever added, stays an implementation detail.
  * Every metric is explained ({metric, meaning, value, source}) so ARIA can
    interpret the structured summaries without rebuilding the numbers (Milestone 10).
  * Report generation is independent of any UI and returns plain structures / CSV
    text, ready for PDF / Excel / CSV / API / scheduled delivery later.
The composition shape is species-neutral, a template for the other livestock modules.
"""

import csv
import io

from sqlalchemy import func, select

from app.models.farm import Farm
from app.models.swine import (
    SwineDiseaseCase,
    SwineMortality,
    SwinePig,
    SwineSale,
    SwineTreatment,
    SwineVaccination,
)
from app.services import (
    swine_breeding_service,
    swine_farrowing_service,
    swine_feed_service,
    swine_finance_service,
    swine_growth_service,
    swine_health_service,
    swine_housing_service,
    swine_service,
)


def _metric(meaning: str, value, source: str, *, unit: str | None = None) -> dict:
    """Wrap a composed value with its meaning and originating engine (rule 4/8)."""
    return {"meaning": meaning, "value": value, "source": source, "unit": unit}


async def _count(db, model, *conds) -> int:
    return (await db.execute(select(func.count(model.id)).where(*conds))).scalar_one() or 0


# ── Individual pig report ──────────────────────────────────────────────────────

async def pig_report(db, farm_id, pig_id) -> dict:
    pig, names, refs = await swine_service.get_pig_detail(db, farm_id, pig_id)
    growth = await swine_growth_service.growth_analysis(db, farm_id, pig_id)
    readiness = await swine_growth_service.market_readiness(db, farm_id, pig_id)
    movements = await swine_service.list_movements(db, farm_id, pig_id, limit=500)
    feed = (await swine_feed_service.feed_summary(db, farm_id, pig_id=pig_id))["summary"]
    sales, _ = await swine_finance_service.list_sales(db, farm_id, pig_id=pig_id)

    health = {
        "disease_cases": _metric("Recorded disease cases involving this pig",
                                 await _count(db, SwineDiseaseCase, SwineDiseaseCase.farm_id == farm_id,
                                              SwineDiseaseCase.pig_id == pig_id, SwineDiseaseCase.deleted_at.is_(None)),
                                 "health"),
        "vaccinations": _metric("Vaccinations administered",
                                await _count(db, SwineVaccination, SwineVaccination.farm_id == farm_id,
                                             SwineVaccination.pig_id == pig_id, SwineVaccination.deleted_at.is_(None)),
                                "health"),
        "treatments": _metric("Treatments recorded",
                              await _count(db, SwineTreatment, SwineTreatment.farm_id == farm_id,
                                           SwineTreatment.pig_id == pig_id, SwineTreatment.deleted_at.is_(None)),
                              "health"),
    }

    breeding = None
    if swine_service.cfg.is_breeding_female(pig.sex):
        breeding = {"role": "dam", **await swine_breeding_service.dam_performance(db, farm_id, pig_id)}
    elif swine_service.cfg.is_intact_male(pig.sex):
        breeding = {"role": "sire", **await swine_breeding_service.sire_performance(db, farm_id, pig_id)}

    financial = {
        "sales": _metric("Sales recorded for this pig", len(sales), "finance"),
        "revenue": _metric("Total sale revenue for this pig",
                           float(sum((s.total_price or 0) for s in sales)), "finance", unit="currency"),
        "feed_cost": feed["total_cost"],
    }

    return {
        "report_type": "pig",
        "pig": {"id": str(pig.id), "internal_ref": pig.internal_ref, "name": pig.name, "sex": pig.sex,
                "production_stage": pig.production_stage, "status": pig.status,
                "breed": names["breed"].get(pig.breed_id), "sire_ref": refs.get(pig.sire_id),
                "dam_ref": refs.get(pig.dam_id)},
        "growth": {"meaning": "Weight history, ADG and growth curve (computed)", "source": "growth", **growth},
        "market_readiness": {"meaning": "Explainable readiness assessment", "source": "growth", **readiness},
        "health_history": health,
        "breeding_history": breeding,
        "movement_history": _metric("Recorded location movements (biosecurity trail)",
                                    len(movements), "registry"),
        "feed": {"meaning": "Feed totals + FCR (computed)", "source": "feed", **feed},
        "financial_contribution": financial,
    }


# ── Litter report ──────────────────────────────────────────────────────────────

async def litter_report(db, farm_id, litter_id) -> dict:
    litter, performance, individuals = await swine_farrowing_service.get_litter_detail(db, farm_id, litter_id)
    growth = await swine_growth_service.cohort_growth(db, farm_id, litter_id=litter_id)
    return {
        "report_type": "litter",
        "litter": {"id": str(litter.id), "litter_code": litter.litter_code, "status": litter.status,
                   "born_alive": litter.born_alive, "weaned": litter.weaned},
        "birth_performance": {"meaning": "Live-birth / stillborn / mummified rates (computed)",
                              "source": "farrowing", **performance},
        "survival": _metric("Pre-wean survival (weaned ÷ born alive)", performance.get("pre_wean_survival_pct"),
                            "farrowing"),
        "weaning": {"weaned": _metric("Piglets weaned", litter.weaned, "farrowing"),
                    "weaning_date": _metric("Weaning date", litter.weaning_date.isoformat()
                                            if litter.weaning_date else None, "farrowing")},
        "growth": {"meaning": "Average weight + ADG of individually-tracked piglets", "source": "growth", **growth},
        "individual_pig_count": _metric("Individually-tracked pigs in this litter", individuals, "registry"),
    }


# ── Pen report ──────────────────────────────────────────────────────────────────

async def pen_report(db, farm_id, pen_id) -> dict:
    pen, occupancy = await swine_housing_service.get_pen_detail(db, farm_id, pen_id)
    growth = await swine_growth_service.cohort_growth(db, farm_id, pen_id=pen_id)
    # Health events touching pigs currently in this pen (recorded facts).
    disease = await _count(db, SwineDiseaseCase, SwineDiseaseCase.farm_id == farm_id,
                           SwineDiseaseCase.pen_id == pen_id, SwineDiseaseCase.deleted_at.is_(None))
    stage_rows = await db.execute(
        select(SwinePig.production_stage, func.count(SwinePig.id)).where(
            SwinePig.farm_id == farm_id, SwinePig.pen_id == pen_id, SwinePig.status == "active",
            SwinePig.deleted_at.is_(None)).group_by(SwinePig.production_stage))
    by_stage = {row[0]: row[1] for row in stage_rows}
    return {
        "report_type": "pen",
        "pen": {"id": str(pen.id), "name": pen.name, "pen_type": pen.pen_type,
                "biosecurity_status": pen.biosecurity_status},
        "occupancy": {"meaning": "Derived occupancy vs capacity", "source": "housing", **occupancy},
        "production_by_stage": _metric("Active pigs by production stage in this pen", by_stage, "registry"),
        "growth": {"meaning": "Average weight + ADG of pigs in this pen", "source": "growth", **growth},
        "health_events": _metric("Disease cases scoped to this pen", disease, "health"),
    }


# ── Farm dashboard (production / finance / health / growth / reproduction) ──────

async def farm_dashboard(db, farm_id) -> dict:
    reproduction = await swine_breeding_service.reproduction_summary(db, farm_id)
    farrowing = await swine_farrowing_service.farrowing_summary(db, farm_id)
    feed = (await swine_feed_service.feed_summary(db, farm_id))["summary"]
    health = await swine_health_service.health_summary(db, farm_id)
    growth = await swine_growth_service.herd_growth_summary(db, farm_id)
    finance = await swine_finance_service.finance_summary(db, farm_id)
    housing = await swine_housing_service.housing_summary(db, farm_id)
    population = await _count(db, SwinePig, SwinePig.farm_id == farm_id,
                              SwinePig.status == "active", SwinePig.deleted_at.is_(None))
    return {
        "report_type": "farm",
        "farm_id": str(farm_id),
        "population": _metric("Active pigs on the farm", population, "registry"),
        "housing": {"meaning": "Occupancy, capacity and biosecurity", "source": "housing", **housing},
        "reproduction": {"meaning": "Service / conception / pregnancy performance", "source": "breeding",
                         **reproduction},
        "farrowing": {"meaning": "Litter size, live-birth and pre-wean survival", "source": "farrowing",
                      **farrowing},
        "feed": {"meaning": "Feed totals, cost and efficiency", "source": "feed", **feed},
        "health": {"meaning": "Cases, mortality, withdrawals (a pattern, not a diagnosis)", "source": "health",
                   **health},
        "growth": {"meaning": "Herd average weight and ADG", "source": "growth", **growth},
        "finance": {"meaning": "P&L and unit economics", "source": "finance", **finance},
    }


# ── Organization report (cross-farm comparison + executive KPIs) ────────────────

async def organization_report(db, farm: Farm) -> dict:
    org_id = farm.organization_id
    if org_id is None:
        farms = [farm]
    else:
        rows = await db.execute(select(Farm).where(Farm.organization_id == org_id, Farm.deleted_at.is_(None)))
        farms = list(rows.scalars().all()) or [farm]

    per_farm = []
    for f in farms:
        fin = await swine_finance_service.finance_summary(db, f.id)
        repro = await swine_breeding_service.reproduction_summary(db, f.id)
        litters = await swine_farrowing_service.farrowing_summary(db, f.id)
        health = await swine_health_service.health_summary(db, f.id)
        population = await _count(db, SwinePig, SwinePig.farm_id == f.id,
                                  SwinePig.status == "active", SwinePig.deleted_at.is_(None))
        per_farm.append({
            "farm_id": str(f.id), "farm_name": getattr(f, "name", None),
            "population": population,
            "gross_margin": fin["pnl"]["gross_margin"]["value"],
            "roi_pct": fin["pnl"]["roi_pct"]["value"],
            "conception_rate_pct": repro["conception_rate_pct"]["value"],
            "avg_litter_size": litters["avg_litter_size"]["value"],
            "mortality_rate_pct": health["mortality_rate_pct"]["value"],
        })

    def _avg(key):
        vals = [p[key] for p in per_farm if isinstance(p.get(key), (int, float))]
        return round(sum(vals) / len(vals), 2) if vals else None

    return {
        "report_type": "organization",
        "organization_id": str(org_id) if org_id else None,
        "farm_count": _metric("Farms in the organisation", len(farms), "registry"),
        "executive_kpis": {
            "total_population": _metric("Total active pigs across farms",
                                        sum(p["population"] for p in per_farm), "registry"),
            "avg_conception_rate_pct": _metric("Mean conception rate across farms",
                                               _avg("conception_rate_pct"), "breeding"),
            "avg_litter_size": _metric("Mean litter size across farms", _avg("avg_litter_size"), "farrowing"),
            "avg_mortality_rate_pct": _metric("Mean mortality rate across farms",
                                              _avg("mortality_rate_pct"), "health"),
            "avg_roi_pct": _metric("Mean ROI across farms", _avg("roi_pct"), "finance"),
        },
        "benchmarking": per_farm,
    }


# ── CSV exports (UI-independent; ready for API / scheduled delivery) ────────────

async def export_registry_csv(db, farm_id) -> str:
    rows = await db.execute(select(SwinePig).where(
        SwinePig.farm_id == farm_id, SwinePig.deleted_at.is_(None)).order_by(SwinePig.internal_ref))
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["internal_ref", "name", "ear_tag", "sex", "birth_sex", "production_stage", "status",
                "current_weight_kg", "date_of_birth"])
    for p in rows.scalars():
        w.writerow([p.internal_ref, p.name or "", p.ear_tag or "", p.sex, p.birth_sex, p.production_stage,
                    p.status, p.current_weight_kg if p.current_weight_kg is not None else "",
                    p.date_of_birth.isoformat() if p.date_of_birth else ""])
    return buf.getvalue()


async def export_sales_csv(db, farm_id) -> str:
    rows = await db.execute(select(SwineSale).where(
        SwineSale.farm_id == farm_id, SwineSale.deleted_at.is_(None)).order_by(SwineSale.sale_date))
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["sale_date", "sale_type", "buyer_name", "head_count", "weight_kg", "total_price", "currency"])
    for s in rows.scalars():
        w.writerow([s.sale_date.isoformat(), s.sale_type, s.buyer_name or "", s.head_count,
                    s.weight_kg if s.weight_kg is not None else "", s.total_price, s.currency or ""])
    return buf.getvalue()


async def export_mortality_csv(db, farm_id) -> str:
    rows = await db.execute(select(SwineMortality).where(
        SwineMortality.farm_id == farm_id, SwineMortality.deleted_at.is_(None)).order_by(SwineMortality.died_on))
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["died_on", "count", "cause_category", "suspected_cause", "confirmed_cause", "disposal_method"])
    for m in rows.scalars():
        w.writerow([m.died_on.isoformat(), m.count, m.cause_category, m.suspected_cause or "",
                    m.confirmed_cause or "", m.disposal_method])
    return buf.getvalue()
