# Aviculture Finance Architecture — Decision & Intentional Limitation

**Status:** Intentional design decision (Module 15, Part 7).
**Audience:** Future contributors touching Aviculture finance, Greena Finance
(Module 5), or the finance dashboard.
**TL;DR:** Aviculture reuses the shared Finance/Inventory engines rather than
building a parallel one. The one place they don't fit — the *flock-centric*
finance dashboard — is a deliberate, documented limitation, **not** an oversight.

---

## The constitutional rule

Document 13 (Implementation Roadmap), Part 7 — Inventory & Finance — mandates:

> **Reuse Greena systems. … Success Criteria: No duplicated finance engine.**

Document 14 (Engineering Standards) reinforces it: single source of truth, never
duplicate calculations, never create competing services.

So Aviculture must **not** create its own expense/revenue tables, its own P&L
calculator, or a competing supplier/inventory system.

## What "reuse" looks like in Aviculture

| Concern | How Aviculture handles it |
|---|---|
| Feed, medication, equipment (stock, consumption, suppliers, assets) | **Reuses the existing farm-level Inventory module unchanged.** No aviculture inventory tables. |
| Expenses (bird purchases, operational costs) | **Posts to the shared `expenses` ledger** via `finance_service.log_expense` / `record_category_expense` (`flock_id=None`), tagged `metadata.module = "aviculture"` for attribution. No aviculture expense table. |
| Income (bird sales) | Recorded as a **fact on the bird's timeline** (`avi_bird_event`, Part 2) with price/buyer. Read back by the aviculture P&L summary. |
| Collection valuation | The only genuinely new concept (appraised/insured/market value of individual birds — championship/rare/breeding stock). It is **not** an expense or revenue, so it gets its own recorded-fact table `avi_valuation`. The *value* is **computed** by the pure `valuation_engine`, never stored as a competing snapshot. |
| Aviculture P&L | **Computed live** by `aviculture_finance_service.finance_summary` from recorded facts (sale/purchase events + shared-ledger expenses + collection value). A *report*, not a storage/calculation engine. |

## The intentional limitation: the flock-centric dashboard

The platform's farm finance **dashboard** (`finance_service.get_finance_dashboard`)
aggregates **only** from `financial_snapshots`, which are **per-flock** and joined
to the `flocks` table. This is frozen:

```python
# get_finance_dashboard: "Aggregates from financial_snapshots only (DB-07 Frozen).
#  No real-time aggregate queries." → SELECT ... JOIN Flock ...
```

Aviculture manages **individual birds, not flocks** (Module 15's founding
distinction — Doc 01 §7). It has no `flock_id`. Therefore:

> **Aviculture income and expenses do not appear in the platform's flock-snapshot
> finance dashboard.** They live in the shared `expenses` ledger and on bird sale
> events, and are surfaced through the **aviculture** finance summary
> (`GET /farms/{id}/aviculture/finance/summary`) and dashboard
> (`GET /farms/{id}/aviculture/reports/dashboard`), all honesty-labelled.

This is a **deliberate boundary**, chosen over the alternatives below.

## Why not make `revenue_records.flock_id` nullable?

It looks tempting (one income ledger). We rejected it:

1. **No benefit for the dashboard.** Even with nullable flock, the finance
   dashboard sums *flock snapshots* only — non-flock revenue would still be
   **invisible** there. `recompute_snapshot` is per-flock and would never include it.
2. **Reverses a tested contract.** `test_finance.py::test_flock_id_required`
   asserts revenue requires a flock — a documented Module 1 behaviour.
3. **Touches a frozen decision.** The snapshot-only dashboard is **DB-07 Frozen**.
4. It would add risk and a half-integration (income stored but unshown) for no
   real gain.

Making it nullable is *risk without benefit*. So we didn't.

## Why not build an aviculture P&L snapshot table?

That **would** be a duplicated finance engine — exactly what Part 7 forbids. The
aviculture P&L is computed on read from recorded facts (evidence-backed, always
current), never frozen into a competing snapshot.

## The future path (if ever needed)

If the platform later introduces a **farm-level (non-flock) revenue** concept and
a farm-wide finance view that isn't snapshot-bound, aviculture income can post to
the central ledger and *both* modules benefit — no aviculture rework required
(the sale facts are already recorded). Until then, the boundary above stands.

## Where the code lives

- `backend/app/services/valuation_engine.py` — pure collection-valuation engine.
- `backend/app/services/aviculture_finance_service.py` — reuse layer + computed P&L.
- `backend/app/services/aviculture_reporting_service.py` — composes engines (Part 8).
- `backend/alembic/versions/059_aviculture_valuation.py` — `avi_valuation` only.
- Reused: `backend/app/services/finance_service.py`, `inventory_service.py`.
