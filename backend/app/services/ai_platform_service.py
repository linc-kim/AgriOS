"""
Greena — ARIA AI Platform Service (Module 9).

Extends the existing ARIA chat with a prediction / forecasting layer, a unified
AI context builder, and an offline-safe natural-language assistant:

  * Context builder — one structured payload across feed, finance, inventory,
    health and production.
  * Forecasts — feed depletion, financial (net-profit projection), inventory,
    egg production; each explainable (contributing factors).
  * Predictions — mortality (trend extrapolation) and disease-risk scoring with
    factor attribution (explainable AI).
  * Ask — grounds an answer in the farm context, served by Gemini → Claude →
    offline fallback (ai_provider), with caching, cost tracking and rate limiting.

All read-only compositions; deterministic where no LLM is configured.
"""

import hashlib
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_platform import AIResponseCache
from app.models.auth import User
from app.models.farm import Farm
from app.models.flock import DailyLog, Flock, ProductionRecord
from app.schemas.ai_platform import (
    AIDashboard,
    AIForecast,
    AIPlatformContext,
    AskResponse,
    DiseaseRisk,
    ExplainFactor,
    ForecastsResponse,
    MortalityPrediction,
)

_DAILY_LIMIT = 200          # per-farm assistant queries/day (rate limit)
_CACHE_TTL_HOURS = 6


def _fid(farm_id) -> str:
    return str(farm_id)


# ── Context builder ───────────────────────────────────────────────────────────

async def build_context(db: AsyncSession, farm: Farm) -> AIPlatformContext:
    from app.services import feed_service, finance_analytics_service, health_service, inventory_service

    feed_dash = await feed_service.get_dashboard(db, farm.id)
    fin = await finance_analytics_service.get_overview(db, farm.id)
    inv = await inventory_service.get_dashboard(db, farm.id)
    health = await health_service.get_farm_health_summary(db, farm)
    prod = await _production_snapshot(db, farm.id)

    return AIPlatformContext(
        farm_id=farm.id, generated_at=datetime.now(tz=timezone.utc),
        feed={"stock_kg": str(feed_dash.total_stock_kg), "stock_value": str(feed_dash.total_stock_value_kes),
              "low_stock": feed_dash.low_stock_count, "consumed_30d": str(feed_dash.consumed_kg),
              "next_purchase": feed_dash.forecast.next_purchase_date.isoformat() if feed_dash.forecast.next_purchase_date else None},
        finance={"cash_balance": str(fin.cash_balance), "revenue_30d": str(fin.m30_revenue),
                 "expenses_30d": str(fin.m30_expenses), "profit_30d": str(fin.m30_profit),
                 "top_expense": fin.top_expense_category.name if fin.top_expense_category else None},
        inventory={"value": str(inv.total_inventory_value), "items": inv.item_count,
                   "low_stock": inv.low_stock_count, "out_of_stock": inv.out_of_stock_count,
                   "expiring": inv.expiring_count, "maintenance_due": inv.maintenance_due_count},
        health={"open_events": health.open_events, "critical_open": health.critical_open,
                "overdue_vaccinations": health.overdue_vaccinations, "active_alerts": health.active_alert_count},
        production=prod,
    )


async def _production_snapshot(db, farm_id) -> dict:
    since = date.today() - timedelta(days=30)
    eggs = await db.execute(select(func.coalesce(func.sum(ProductionRecord.eggs_collected), 0)).where(
        ProductionRecord.farm_id == _fid(farm_id), ProductionRecord.deleted_at.is_(None), ProductionRecord.record_date >= since))
    mort = await db.execute(select(func.coalesce(func.sum(DailyLog.mortality_count), 0)).where(
        DailyLog.farm_id == _fid(farm_id), DailyLog.deleted_at.is_(None), DailyLog.log_date >= since))
    flocks = await db.execute(select(func.count(Flock.id)).where(
        Flock.farm_id == _fid(farm_id), Flock.deleted_at.is_(None), Flock.status == "active"))
    return {"eggs_30d": int(eggs.scalar_one()), "mortality_30d": int(mort.scalar_one()),
            "active_flocks": int(flocks.scalar_one())}


# ── Mortality prediction (explainable) ────────────────────────────────────────

async def predict_mortality(db: AsyncSession, farm: Farm) -> MortalityPrediction:
    """Predict next-7-day mortality by comparing the last two weeks' trend."""
    today = date.today()
    recent = await _mortality_sum(db, farm.id, today - timedelta(days=6), today)
    prior = await _mortality_sum(db, farm.id, today - timedelta(days=13), today - timedelta(days=7))

    if prior == 0 and recent == 0:
        predicted, trend, conf = 0, "stable", "low"
    else:
        # Simple momentum: project recent adjusted by the week-over-week change.
        delta = recent - prior
        predicted = max(0, int(round(recent + delta * 0.5)))
        if delta > max(2, prior * 0.2):
            trend = "rising"
        elif delta < -max(2, prior * 0.2):
            trend = "falling"
        else:
            trend = "stable"
        conf = "high" if (recent + prior) >= 20 else "medium" if (recent + prior) >= 5 else "low"

    factors = [
        ExplainFactor(factor="Recent 7-day deaths", impact=f"{recent}", detail="Primary signal for the projection."),
        ExplainFactor(factor="Prior 7-day deaths", impact=f"{prior}", detail="Baseline for week-over-week trend."),
        ExplainFactor(factor="Trend", impact=trend, detail="Direction of the momentum term."),
    ]
    health = await _open_critical(db, farm.id)
    if health > 0:
        factors.append(ExplainFactor(factor="Open critical health events", impact=f"+{health}",
                                     detail="Active disease/critical events raise expected mortality."))
        if predicted == 0:
            predicted = health
    explanation = (
        f"Projected ~{predicted} death(s) over the next 7 days: the last week saw {recent} "
        f"(vs {prior} the week before), a {trend} trend."
    )
    return MortalityPrediction(scope="farm", predicted_next_7d=predicted, recent_7d=recent, trend=trend,
                               confidence=conf, factors=factors, explanation=explanation)


async def _mortality_sum(db, farm_id, s, e) -> int:
    res = await db.execute(select(func.coalesce(func.sum(DailyLog.mortality_count + DailyLog.culls), 0)).where(
        DailyLog.farm_id == _fid(farm_id), DailyLog.deleted_at.is_(None), DailyLog.log_date >= s, DailyLog.log_date <= e))
    return int(res.scalar_one())


async def _open_critical(db, farm) -> int:
    from app.services import health_service
    summary = await health_service.get_farm_health_summary(db, farm if isinstance(farm, Farm) else await _farm(db, farm))
    return summary.critical_open


async def _farm(db, farm_id) -> Farm:
    res = await db.execute(select(Farm).where(Farm.id == _fid(farm_id)))
    return res.scalar_one()


# ── Disease risk scoring (explainable AI) ─────────────────────────────────────

async def disease_risk(db: AsyncSession, farm: Farm) -> DiseaseRisk:
    from app.services import health_service
    summary = await health_service.get_farm_health_summary(db, farm)
    recent_deaths = await _mortality_sum(db, farm.id, date.today() - timedelta(days=7), date.today())

    score = 0
    factors: list[ExplainFactor] = []

    if summary.critical_open > 0:
        pts = min(40, summary.critical_open * 20)
        score += pts
        factors.append(ExplainFactor(factor="Critical open health events", impact=f"+{pts}",
                                      detail=f"{summary.critical_open} critical event(s)."))
    if summary.active_alert_count > 0:
        pts = min(20, summary.active_alert_count * 10)
        score += pts
        factors.append(ExplainFactor(factor="Active disease alerts in your area", impact=f"+{pts}",
                                      detail=f"{summary.active_alert_count} regional alert(s)."))
    if summary.overdue_vaccinations > 0:
        pts = min(20, summary.overdue_vaccinations * 5)
        score += pts
        factors.append(ExplainFactor(factor="Overdue vaccinations", impact=f"+{pts}",
                                      detail=f"{summary.overdue_vaccinations} overdue — reduced immunity."))
    if recent_deaths >= 10:
        pts = min(25, recent_deaths)
        score += pts
        factors.append(ExplainFactor(factor="Elevated recent mortality", impact=f"+{pts}",
                                      detail=f"{recent_deaths} death(s) in 7 days."))
    if summary.open_events > 0 and summary.critical_open == 0:
        score += 5
        factors.append(ExplainFactor(factor="Open (non-critical) health events", impact="+5",
                                      detail=f"{summary.open_events} open event(s)."))

    score = min(100, score)
    if score >= 70:
        level, rec = "critical", "Isolate affected birds, call your vet today, and review biosecurity immediately."
    elif score >= 40:
        level, rec = "high", "Increase monitoring, clear overdue vaccinations, and tighten biosecurity."
    elif score >= 15:
        level, rec = "moderate", "Keep monitoring; address overdue vaccinations and any open health events."
    else:
        level, rec = "low", "No elevated disease signals — maintain routine biosecurity and vaccination."
    if not factors:
        factors.append(ExplainFactor(factor="No adverse signals", impact="0", detail="Health, alerts and mortality are all nominal."))

    return DiseaseRisk(score=score, level=level, factors=factors, recommendation=rec)


# ── Forecasts ─────────────────────────────────────────────────────────────────

async def get_forecasts(db: AsyncSession, farm: Farm) -> ForecastsResponse:
    from app.services import feed_service, finance_analytics_service, inventory_service

    # Feed depletion.
    fc = await feed_service.get_forecast(db, farm.id)
    feed_fore = AIForecast(
        metric="Feed depletion", horizon_days=30,
        projected_value=fc.soonest_depletion_date.isoformat() if fc.soonest_depletion_date else "no depletion in window",
        unit="date", confidence="high" if fc.items_needing_purchase else "medium",
        factors=[f"{fc.items_needing_purchase} item(s) need purchase",
                 f"next purchase by {fc.next_purchase_date.isoformat()}" if fc.next_purchase_date else "stock stable"],
        series=[{"period": i.feed_type, "days_remaining": i.days_remaining} for i in fc.items[:6] if i.days_remaining is not None],
    )

    # Financial — project next 30d net from recent monthly trend.
    an = await finance_analytics_service.get_analytics(db, farm.id)
    trend = an.revenue_trend[-3:] if an.revenue_trend else []
    if trend:
        avg_net = sum((Decimal(p.profit) for p in trend), Decimal("0")) / len(trend)
    else:
        avg_net = Decimal("0")
    fin_fore = AIForecast(
        metric="Net profit (next 30 days)", horizon_days=30,
        projected_value=str(avg_net.quantize(Decimal("0.01"))), unit="KES",
        confidence="medium" if len(trend) >= 2 else "low",
        factors=["Projected from the last 3 months' average monthly net profit."],
        series=[{"period": p.period, "profit": str(p.profit)} for p in an.revenue_trend[-6:]],
    )

    # Inventory — consumption-based reorder pressure.
    inv_an = await inventory_service.get_analytics(db, farm.id)
    inv_fore = AIForecast(
        metric="Inventory reorder pressure", horizon_days=30,
        projected_value=str(len(inv_an.reorder_recommendations)), unit="items to reorder",
        confidence="high" if inv_an.reorder_recommendations else "low",
        factors=[f"{len(inv_an.reorder_recommendations)} item(s) at/under reorder level",
                 f"inventory valued at KES {inv_an.inventory_valuation:,}"],
        series=[{"period": r.name, "suggested": str(r.suggested_order_qty)} for r in inv_an.reorder_recommendations[:6]],
    )

    # Production — project 30d eggs from the last 30d run-rate.
    prod = await _production_snapshot(db, farm.id)
    prod_fore = AIForecast(
        metric="Egg production (next 30 days)", horizon_days=30,
        projected_value=str(prod["eggs_30d"]), unit="eggs",
        confidence="medium" if prod["eggs_30d"] > 0 else "low",
        factors=[f"Run-rate from the last 30 days ({prod['eggs_30d']} eggs).",
                 f"{prod['active_flocks']} active flock(s)."],
        series=[],
    )

    return ForecastsResponse(feed=feed_fore, financial=fin_fore, inventory=inv_fore, production=prod_fore)


# ── Assistant (offline-safe) ──────────────────────────────────────────────────

# Words that mark "production" as meaning the deployed system rather than the
# farm's egg output.
_OPS_MARKERS = (
    "environment", "deploy", "release", "server", "system", "uptime",
    "healthy", "unhealthy", "degraded", "incident", "outage", "version",
    "database", "migration", "backup", "monitoring", "diagnostics",
)

# Any of these makes a question operational enough to be worth loading the ops
# context, which runs a diagnostic sweep and so is not free.
_OPS_TRIGGERS = _OPS_MARKERS + (
    "restore", "snapshot", "diagnostic", "rollback", "metric", "latency",
    "slow", "error rate", "traffic", "import", "export", "download", "upload",
    "csv", "spreadsheet", "production",
)


def needs_ops_context(question: str) -> bool:
    q = question.lower()
    return any(trigger in q for trigger in _OPS_TRIGGERS)


def _is_ops_question(q: str) -> bool:
    """True when a question mentioning "production" means the deployment."""
    return any(marker in q for marker in _OPS_MARKERS)


async def collect_ops_context(db: AsyncSession, farm: Farm) -> dict:
    """
    Gather the production-readiness facts ARIA answers from (Module 11).

    Every value is read live from the system, so ARIA reports what is actually
    true rather than a plausible-sounding guess. Each block is independently
    guarded: an operational question must still get a partial answer if one
    subsystem cannot be read.
    """
    from sqlalchemy import func as sa_func

    from app.models.production import Backup, ExportJob, ImportJob
    from app.services import diagnostics_service, metrics_service, release_service

    ops: dict = {}

    try:
        result = await db.execute(
            select(Backup)
            .where(Backup.farm_id == farm.id, Backup.deleted_at.is_(None))
            .order_by(Backup.created_at.desc())
        )
        backups = list(result.scalars().all())
        latest = backups[0] if backups else None
        ops["backups"] = {
            "total": len(backups),
            "failed": sum(1 for b in backups if b.status == "failed"),
            "latest_at": latest.created_at.strftime("%Y-%m-%d %H:%M") if latest else None,
            "latest_status": latest.status if latest else None,
            "latest_size_kb": round(latest.size_bytes / 1024, 1) if latest else 0,
        }
    except Exception:
        pass

    try:
        report = await diagnostics_service.run_diagnostics(db)
        ops["diagnostics"] = {
            "status": report["status"],
            "passed": report["passed_count"],
            "total": len(report["checks"]),
            "failing": [c["name"] for c in report["checks"] if not c["passed"]],
        }
    except Exception:
        pass

    try:
        info = release_service.version_info()
        current = await release_service.current_migration_revision(db)
        expected = release_service.expected_migration_revision()
        latest_release = await release_service.latest_release(db)
        ops["release"] = {
            "version": info["version"],
            "environment": info["environment"],
            "git_sha_short": info["git_sha_short"],
            "uptime_hours": round(info["uptime_seconds"] / 3600, 1),
            "migration_current": current,
            "migration_expected": expected,
            "migrations_at_head": bool(current and expected and current == expected),
            "is_rollback": bool(latest_release and latest_release.is_rollback),
        }
    except Exception:
        pass

    try:
        summary = metrics_service.registry.summary()
        slowest = summary["slowest_routes"][0] if summary["slowest_routes"] else None
        ops["metrics"] = {
            "total_requests": summary["total_requests"],
            "error_rate_pct": round(summary["error_rate"] * 100, 2),
            "avg_latency_ms": summary["avg_latency_ms"],
            "slowest": f"{slowest['path']} at {slowest['avg_ms']} ms" if slowest else None,
        }
    except Exception:
        pass

    try:
        exports = await db.execute(
            select(sa_func.count(ExportJob.id)).where(
                ExportJob.farm_id == farm.id, ExportJob.deleted_at.is_(None))
        )
        imports = await db.execute(
            select(ImportJob.status).where(
                ImportJob.farm_id == farm.id, ImportJob.deleted_at.is_(None))
        )
        import_statuses = [r for r in imports.scalars().all()]
        ops["data_io"] = {
            "exports": int(exports.scalar() or 0),
            "imports": len(import_statuses),
            "failed_imports": sum(1 for s in import_statuses if s == "failed"),
        }
    except Exception:
        pass

    return ops


def _build_offline_answer(question: str, ctx: AIPlatformContext, extra: dict) -> tuple[str, list[str]]:
    """A grounded, deterministic answer from the farm context, used when no LLM
    is configured or providers fail. Returns (answer, sources)."""
    q = question.lower()
    parts: list[str] = []
    sources: list[str] = []

    def add(section, text):
        parts.append(text)
        if section not in sources:
            sources.append(section)

    matched = False
    if any(w in q for w in ("feed", "reorder", "depletion")):
        matched = True
        add("feed", f"Feed: {ctx.feed['stock_kg']} kg on hand (value KES {ctx.feed['stock_value']}), "
                    f"{ctx.feed['low_stock']} item(s) low. "
                    + (f"Next purchase advised by {ctx.feed['next_purchase']}." if ctx.feed.get('next_purchase') else "Stock is stable."))
    if any(w in q for w in ("profit", "finance", "money", "cash", "revenue", "expense", "cost")):
        matched = True
        add("finance", f"Finance: 30-day revenue KES {ctx.finance['revenue_30d']}, expenses KES {ctx.finance['expenses_30d']}, "
                       f"net KES {ctx.finance['profit_30d']}; cash balance KES {ctx.finance['cash_balance']}."
                       + (f" Top expense: {ctx.finance['top_expense']}." if ctx.finance.get('top_expense') else ""))
    if any(w in q for w in ("mortality", "death", "die", "dying")):
        matched = True
        m = extra.get("mortality")
        if m:
            add("health", f"Mortality: {m['recent_7d']} death(s) in the last 7 days ({m['trend']} trend); "
                          f"~{m['predicted_next_7d']} projected next 7 days.")
    if any(w in q for w in ("disease", "risk", "sick", "health", "outbreak")):
        matched = True
        r = extra.get("risk")
        if r:
            add("health", f"Disease risk: {r['score']}/100 ({r['level']}). {r['recommendation']}")
    if any(w in q for w in ("inventory", "stock", "asset", "maintenance", "supplies")):
        matched = True
        add("inventory", f"Inventory: KES {ctx.inventory['value']} across {ctx.inventory['items']} item(s); "
                         f"{ctx.inventory['low_stock']} low, {ctx.inventory['out_of_stock']} out, "
                         f"{ctx.inventory['expiring']} expiring; {ctx.inventory['maintenance_due']} asset(s) need service.")
    if any(w in q for w in ("egg", "lay", "hatch")) or (
        "production" in q and not _is_ops_question(q)
    ):
        matched = True
        add("production", f"Production: {ctx.production['eggs_30d']} eggs in the last 30 days across "
                          f"{ctx.production['active_flocks']} active flock(s).")

    # ── Module 11: operational topics ─────────────────────────────────────────
    # "production" is deliberately ambiguous in this domain — it means both egg
    # output and the deployed environment. _is_ops_question decides which sense
    # is meant, so "how is production doing?" still answers about the flock while
    # "is production healthy?" answers about the system.
    ops = extra.get("ops") or {}

    if any(w in q for w in ("backup", "restore", "snapshot")):
        matched = True
        b = ops.get("backups")
        if b:
            latest = b["latest_at"] or "never"
            add("backups", (
                f"Backups: {b['total']} stored for this farm, most recent {latest}"
                + (f" ({b['latest_size_kb']} KB, {b['latest_status']})." if b["total"] else ".")
                + (f" {b['failed']} failed backup(s) need attention." if b["failed"] else "")
                + (" No backup has been taken yet — create one before the next data change."
                   if not b["total"] else "")
            ))

    if any(w in q for w in ("diagnostic", "healthy", "system health", "unhealthy", "degraded")):
        matched = True
        d = ops.get("diagnostics")
        if d:
            failing = ", ".join(d["failing"]) if d["failing"] else "none"
            add("diagnostics", (
                f"System diagnostics: {d['status']} — {d['passed']} of {d['total']} checks passing. "
                f"Failing: {failing}."
            ))

    if any(w in q for w in ("deploy", "release", "version", "rollback", "rolled back")):
        matched = True
        r = ops.get("release")
        if r:
            add("release", (
                f"Release: running v{r['version']} in {r['environment']}"
                + (f" ({r['git_sha_short']})" if r.get("git_sha_short") else "")
                + f", up {r['uptime_hours']}h. Migrations "
                + ("at head." if r["migrations_at_head"] else f"BEHIND — database at {r['migration_current']}, code expects {r['migration_expected']}.")
                + (" The last deployment was a rollback." if r.get("is_rollback") else "")
            ))

    if any(w in q for w in ("monitor", "metric", "latency", "slow", "error rate", "uptime", "traffic")):
        matched = True
        m = ops.get("metrics")
        if m:
            add("monitoring", (
                f"Monitoring: {m['total_requests']} requests since restart, "
                f"{m['error_rate_pct']}% server-error rate, {m['avg_latency_ms']} ms average response. "
                + (f"Slowest route: {m['slowest']}." if m.get("slowest") else "No route timings yet.")
            ))

    if any(w in q for w in ("import", "export", "download", "upload", "csv", "spreadsheet")):
        matched = True
        io_stats = ops.get("data_io")
        if io_stats:
            add("data", (
                f"Data transfer: {io_stats['exports']} export(s) and {io_stats['imports']} import(s) recorded"
                + (f", {io_stats['failed_imports']} import(s) failed." if io_stats["failed_imports"] else ".")
            ))

    if not matched:
        add("finance", f"Here's a quick snapshot — 30-day net profit KES {ctx.finance['profit_30d']}, cash KES {ctx.finance['cash_balance']}.")
        add("feed", f"Feed stock {ctx.feed['stock_kg']} kg ({ctx.feed['low_stock']} low).")
        add("health", f"Health: {ctx.health['open_events']} open event(s), {ctx.health['critical_open']} critical.")
        parts.append("Ask me about feed, finances, mortality, disease risk, inventory or egg production for more detail.")

    answer = " ".join(parts)
    return answer, sources


async def _rate_remaining(db, farm_id) -> int:
    since = datetime.now(tz=timezone.utc) - timedelta(hours=24)
    res = await db.execute(select(func.count(AIResponseCache.id)).where(
        AIResponseCache.farm_id == _fid(farm_id), AIResponseCache.created_at >= since))
    used = int(res.scalar_one())
    return max(0, _DAILY_LIMIT - used)


async def ask(db: AsyncSession, farm: Farm, user: User, question: str,
              conversation_id: Optional[uuid.UUID] = None) -> AskResponse:
    from app.exceptions import ValidationException

    remaining = await _rate_remaining(db, farm.id)
    if remaining <= 0:
        raise ValidationException("Daily AI query limit reached. Please try again tomorrow.")

    prompt_hash = hashlib.sha256(f"{farm.id}:{question.strip().lower()}".encode()).hexdigest()

    # Cache hit within TTL.
    cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=_CACHE_TTL_HOURS)
    res = await db.execute(select(AIResponseCache).where(
        AIResponseCache.farm_id == _fid(farm.id), AIResponseCache.prompt_hash == prompt_hash,
        AIResponseCache.deleted_at.is_(None), AIResponseCache.created_at >= cutoff)
        .order_by(AIResponseCache.created_at.desc()).limit(1))
    cached = res.scalar_one_or_none()
    if cached is not None:
        cached.hits += 1
        await db.commit()
        return AskResponse(answer=cached.response, provider=cached.provider, cached=True,
                           tokens=cached.tokens, cost_usd="0.00000000",
                           sources=cached.ai_context.get("sources", []), rate_limit_remaining=remaining)

    # Build grounded context + offline answer, then let the provider layer decide.
    ctx = await build_context(db, farm)
    mortality = await predict_mortality(db, farm)
    risk = await disease_risk(db, farm)

    # Operational context is only gathered for operational questions — it runs a
    # diagnostic sweep, which is too costly to attach to every "how are my
    # birds?" question.
    extra: dict = {"mortality": mortality.model_dump(), "risk": risk.model_dump()}
    if needs_ops_context(question):
        extra["ops"] = await collect_ops_context(db, farm)

    offline_answer, sources = _build_offline_answer(question, ctx, extra)

    prompt = (
        "You are ARIA, a concise poultry-farm assistant. Answer the farmer's question using ONLY the "
        f"structured farm context. Context: {ctx.model_dump_json()}."
        + (f" Operational status: {extra['ops']}." if "ops" in extra else "")
        + f" Question: {question}"
    )
    from app.services import ai_provider
    result = await ai_provider.complete(prompt, offline_answer=offline_answer)

    row = AIResponseCache(
        farm_id=farm.id, prompt_hash=prompt_hash, question=question, response=result.text,
        provider=result.provider, tokens=result.prompt_tokens + result.completion_tokens,
        ai_context={"sources": sources})
    db.add(row)
    await db.commit()

    return AskResponse(answer=result.text, provider=result.provider, cached=False,
                       tokens=result.prompt_tokens + result.completion_tokens,
                       cost_usd=f"{result.cost_usd:.8f}", sources=sources, rate_limit_remaining=remaining - 1)


# ── Dashboard ─────────────────────────────────────────────────────────────────

async def get_dashboard(db: AsyncSession, farm: Farm) -> AIDashboard:
    from app.services import ai_provider, aria_service

    forecasts = await get_forecasts(db, farm)
    mortality = await predict_mortality(db, farm)
    risk = await disease_risk(db, farm)

    # Reuse existing ARIA insights + recommendations if available.
    recs, insights = [], []
    try:
        rec_list = await aria_service.list_recommendations(db, farm.id)
        recs = [{"title": getattr(r, "title", ""), "type": getattr(r, "recommendation_type", "")} for r in (rec_list or [])][:5]
    except Exception:
        recs = []
    try:
        ins_list = await aria_service.list_insights(db, farm.id)
        insights = [{"title": getattr(i, "title", ""), "severity": getattr(i, "severity", "")} for i in (ins_list or [])][:5]
    except Exception:
        insights = []

    headline = (
        f"Disease risk {risk.level} ({risk.score}/100); ~{mortality.predicted_next_7d} deaths projected next week; "
        f"net profit forecast KES {forecasts.financial.projected_value if forecasts.financial else '—'}."
    )
    return AIDashboard(
        generated_at=datetime.now(tz=timezone.utc), providers=ai_provider.providers_available(),
        forecasts=forecasts, mortality=mortality, disease_risk=risk,
        recommendations=recs, insights=insights, headline=headline,
    )
