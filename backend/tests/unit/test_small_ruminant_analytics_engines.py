"""
Small Ruminant Forecast + Bottleneck engines (Modules 18/19, Milestone 9) — PURE.

Forecasts are always labelled 'forecast' with method/assumptions and become
'unknown' without an input window; the bottleneck engine only evaluates supplied
metrics and ranks by severity — nothing fabricated.
"""

from app.services import small_ruminant_forecast_engine as fc
from app.services import small_ruminant_bottleneck_engine as bn


# ── Forecast ───────────────────────────────────────────────────────────────────

def test_project_stock_is_forecast_labelled():
    r = fc.project_stock(100, monthly_births=10, monthly_deaths=2, monthly_sales=3, months=6)
    assert r["label"] == "forecast"
    assert r["value"] == 100 + (10 - 2 - 3) * 6   # 130
    assert "assumptions" in r and r["confidence"] in ("low", "medium", "high")


def test_project_stock_unknown_without_window():
    assert fc.project_stock(None, 1, 1, 1, 6)["label"] == "unknown"
    assert fc.project_stock(100, 1, 1, 1, 0)["label"] == "unknown"


def test_project_flow_and_capacity():
    off = fc.project_flow(5, 4, metric="offspring")
    assert off["label"] == "forecast" and off["value"] == 20
    cap = fc.capacity_requirement(50, 1.5, resource="feed_kg")
    assert cap["value"] == 75.0


# ── Bottlenecks ────────────────────────────────────────────────────────────────

def _lab(v):
    return {"label": "calculated", "value": v}


def test_bottlenecks_only_evaluate_supplied_metrics_and_rank():
    issues = bn.analyze(
        reproduction={"birth_rate_pct": _lab(30)},                 # high (below 40)
        health={"mortality_rate_pct": _lab(6),                     # medium
                "deworming_compliance": {"overdue": _lab(2)}},     # medium
        finance={"pnl": {"gross_margin": _lab(-100)}},             # high
    )
    areas = [i["area"] for i in issues]
    assert "reproduction" in areas and "profitability" in areas and "parasite_control" in areas
    # Highest severity first.
    assert issues[0]["severity"] == "high"
    # Housing/feed weren't supplied → not evaluated (no fabricated issues).
    assert "housing" not in areas and "feed_efficiency" not in areas


def test_bottlenecks_skip_unknown_metrics():
    issues = bn.analyze(reproduction={"birth_rate_pct": {"label": "unknown", "value": None}})
    assert issues == []  # an unknown metric is never treated as a problem
