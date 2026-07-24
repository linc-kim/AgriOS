"""
ARIA — decision support.

Farmers ask ARIA judgement questions: "can I afford another flock?", "should I
change feed?", "should I vaccinate today?". This module answers them the way a
good manager would — laying out the case rather than pronouncing a verdict.

Every answer carries pros, cons, assumptions, risks and, crucially, what
information is missing. ARIA never pretends certainty: where the data needed to
decide isn't recorded, it says so and asks for it instead of guessing. The
recommendation is a lean ("worth considering" / "hold off" / "need more info"),
never a command, because the farmer owns the decision and the consequences.

All deterministic, all from `FarmFacts` — no model, no fabricated numbers.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal

from app.services.aria_intelligence import FarmFacts


@dataclass
class Decision:
    question: str
    lean: str                    # consider | caution | hold | need_info
    headline: str
    pros: list[str] = field(default_factory=list)
    cons: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)


def _kes(v) -> str:
    try:
        return f"KES {int(v):,}"
    except Exception:
        return str(v)


def _decide_new_flock(f: FarmFacts) -> Decision:
    d = Decision(
        question="Can I afford another flock?",
        lean="need_info",
        headline="",
        sources=["Finance", "Livestock"],
    )

    if f.is_profitable is None or f.gross_profit is None:
        d.missing.append("Recent finance data — log expenses and revenue so ARIA can judge affordability.")
    else:
        if f.is_profitable and f.gross_profit > 0:
            d.pros.append(f"The farm is currently profitable ({_kes(f.gross_profit)} gross).")
            d.lean = "consider"
        else:
            d.cons.append("The farm isn't currently profitable — adding birds adds cost before it adds income.")
            d.lean = "caution"

    if f.disease_level in ("high", "critical"):
        d.cons.append(f"Disease risk is {f.disease_level} — bringing in new stock now raises the chance of spreading it.")
        d.risks.append("New birds can introduce or catch disease during an active risk period.")
        if d.lean == "consider":
            d.lean = "caution"

    if f.vaccinations_overdue > 0:
        d.cons.append(f"{f.vaccinations_overdue} vaccination(s) are already overdue on your current flock.")

    d.pros.append("More birds can spread fixed costs (housing, labour) across more output.")
    d.assumptions = [
        "You have housing and feed capacity for the extra birds.",
        "Day-old chick and feed prices are close to what you've been paying.",
    ]
    d.risks.append("A new flock ties up cash for weeks before it earns anything.")
    d.missing.append("Available housing space and your cash on hand — ARIA can't see these.")

    if d.lean == "consider":
        d.headline = "The numbers lean towards yes, but confirm housing, cash and disease risk first."
    elif d.lean == "caution":
        d.headline = "Possible, but there are reasons to wait — weigh these before committing."
    else:
        d.headline = "I can't judge affordability without recent finance data."
    return d


def _decide_change_feed(f: FarmFacts) -> Decision:
    d = Decision(
        question="Should I change feed?",
        lean="need_info",
        headline="",
        sources=["Feed", "Production", "Finance"],
    )

    if f.feed_cost_pct is not None and float(f.feed_cost_pct) >= 65:
        d.pros.append(f"Feed is {f.feed_cost_pct}% of your costs — a better-value feed would move your margin most.")
        d.lean = "consider"
    if f.hen_day_pct is not None and f.hen_day_pct < 60:
        d.pros.append(f"Laying is below par ({f.hen_day_pct:.0f}% hen-day); nutrition is one thing that can lift it.")
        d.lean = "consider"

    d.cons.append("Abrupt feed changes upset the gut and can dip production for a few days.")
    d.assumptions = [
        "The alternative feed matches the stage your birds are at (starter/grower/layer).",
        "You can transition gradually rather than switching overnight.",
    ]
    d.risks.append("A cheaper feed that's lower quality costs more in lost growth or eggs than it saves.")
    d.missing.append("The price and specification of the feed you're comparing — tell ARIA and it can weigh it up.")

    if f.hen_day_pct is None:
        d.missing.append("Current laying rate — log egg production so ARIA can tell if feed is the problem.")

    if d.lean == "consider":
        d.headline = "There's a case for it — but transition gradually and match the ration to the birds' stage."
    else:
        d.headline = "No strong signal to change feed right now; the current ration isn't obviously the problem."
        d.lean = "caution"
    return d


def _decide_vaccinate_today(f: FarmFacts) -> Decision:
    d = Decision(
        question="Should I vaccinate today?",
        lean="need_info",
        headline="",
        sources=["Health"],
    )
    due_now = f.vaccinations_overdue + f.vaccinations_due_today
    if f.vaccinations_overdue > 0:
        d.pros.append(f"{f.vaccinations_overdue} vaccination(s) are overdue — the sooner you catch up, the better.")
        d.lean = "consider"
    elif f.vaccinations_due_today > 0:
        d.pros.append(f"{f.vaccinations_due_today} vaccination(s) are due today.")
        d.lean = "consider"
    elif f.vaccinations_due_week > 0:
        d.headline = f"Nothing is due today, but {f.vaccinations_due_week} vaccination(s) fall due this week."
        d.lean = "caution"
        d.pros.append("Getting ahead of a due-this-week dose avoids it slipping into overdue.")
    else:
        d.headline = "Nothing is due today or this week — no need to vaccinate now."
        d.lean = "hold"
        return d

    d.cons.append("Only vaccinate healthy birds — vaccinating sick birds can make things worse.")
    d.assumptions = ["The vaccine is in stock and has been kept cold."]
    d.risks.append("A broken cold chain means the dose may not protect, even if given on time.")
    if not d.headline:
        d.headline = "Yes — there are doses due, and on-time vaccination is your cheapest protection."
    return d


#: Matched most-specific first.
_DECIDERS = [
    (re.compile(r"another flock|more chicks|buy chicks|new flock|expand|afford.*(flock|chicks|birds)", re.I), _decide_new_flock),
    (re.compile(r"change feed|switch feed|different feed|new feed|better feed", re.I), _decide_change_feed),
    (re.compile(r"vaccinat", re.I), _decide_vaccinate_today),
]


def looks_like_decision(question: str) -> bool:
    q = question or ""
    if not re.search(r"\bshould i\b|\bcan i\b|\bis it worth\b|\bafford\b|\bought i\b", q, re.I):
        return False
    return any(rx.search(q) for rx, _ in _DECIDERS)


def decide(question: str, facts: FarmFacts) -> Decision | None:
    """Return a structured decision, or None if it isn't a decision we cover."""
    if not looks_like_decision(question):
        return None
    for rx, fn in _DECIDERS:
        if rx.search(question):
            return fn(facts)
    return None
