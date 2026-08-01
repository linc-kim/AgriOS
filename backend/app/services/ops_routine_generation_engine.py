"""
Greena — Operations Planner: Routine Generation Engine (deterministic, pure).

Turns a farm profile plus enterprise templates into a set of *proposed* routines
(spec Doc 4 §5, Doc 2 §17). The output is a strategic recommendation: every
generated routine is editable and requires user approval before activation
(spec Doc 6 §5). Pure and deterministic — the same profile + templates always
yield the same proposal; nothing about the farm is invented.

Profile dict::  {"module":"poultry","enterprise_type":"layer",
                "farm_size":500,"labor_available":2,"production_system":"cage",
                "infrastructure":[...],"equipment":[...],"goals":[...]}
Template dict:: an ``ops_routine_template`` row as a dict (default_schedule,
                default_task_templates, category, module, enterprise_type, …)
"""

from __future__ import annotations

from app.services import ops_common as oc

# How much a farm's scale nudges an estimated duration. Deterministic bands, not
# a model — larger operations take longer at the same routine.
_SIZE_BANDS = ((100, 1.0), (500, 1.3), (2000, 1.7), (float("inf"), 2.2))


def _size_multiplier(farm_size) -> float:
    try:
        n = float(farm_size)
    except (TypeError, ValueError):
        return 1.0
    for ceiling, mult in _SIZE_BANDS:
        if n <= ceiling:
            return mult
    return 1.0


def generate(profile: dict, templates: list[dict]) -> dict:
    """Propose routines by selecting templates matching the farm's module and
    enterprise type, scaling estimated effort to farm size.

    Returns ``{"proposed": [...], "basis": {...}, "limitations": [...]}``. When
    the profile is thin, the limitations list says so — no defaults are invented.
    """
    module = (profile.get("module") or "").lower()
    enterprise = (profile.get("enterprise_type") or "").lower()
    size_mult = _size_multiplier(profile.get("farm_size"))

    limitations = []
    if not module:
        limitations.append("No module recorded — cannot match enterprise templates.")
    if profile.get("farm_size") in (None, ""):
        limitations.append("No farm size recorded — durations use the base estimate.")
    if profile.get("labor_available") in (None, ""):
        limitations.append("Labour availability unknown — assignments are left unset.")

    matches = []
    for tpl in templates:
        tpl_mod = (tpl.get("module") or "").lower()
        if module and tpl_mod and tpl_mod != module:
            continue
        tpl_ent = (tpl.get("enterprise_type") or "").lower()
        # Enterprise is a soft filter: an exact match ranks first, generic (blank)
        # templates are still eligible.
        rank = 0 if (enterprise and tpl_ent == enterprise) else 1 if not tpl_ent else 2
        if enterprise and tpl_ent and tpl_ent != enterprise and rank == 2:
            continue
        matches.append((rank, tpl))

    matches.sort(key=lambda rt: (rt[0], str(rt[1].get("name") or "")))

    proposed = []
    for _rank, tpl in matches:
        base_minutes = tpl.get("estimated_time_minutes")
        est = round(base_minutes * size_mult) if base_minutes else None
        proposed.append({
            "name": tpl.get("name"),
            "module": tpl_mod_or(module, tpl),
            "category": tpl.get("category", "administration"),
            "schedule": dict(tpl.get("default_schedule") or {}),
            "task_templates": list(tpl.get("default_task_templates") or []),
            "sops": list(tpl.get("default_sops") or []),
            "checklists": list(tpl.get("default_checklists") or []),
            "estimated_duration_minutes": (
                oc.calculated(est, "Template estimate × farm-size band.")
                if est is not None else oc.unknown("Template has no time estimate.")),
            "source_template_id": tpl.get("id"),
            "status": oc.recommendation(
                "proposed", "Generated from a matching enterprise template; edit before activating.",
                confidence="medium",
                limitations="A starting point — adjust to your infrastructure, labour and goals."),
        })

    return {
        "proposed": proposed,
        "basis": {
            "module": oc.recorded(module or None, "From the farm profile."),
            "enterprise_type": oc.recorded(enterprise or None, "From the farm profile."),
            "farm_size_multiplier": oc.calculated(size_mult, "Applied to duration estimates."),
            "templates_matched": oc.calculated(len(proposed), "Templates that fit this enterprise."),
        },
        "limitations": limitations,
    }


def tpl_mod_or(module: str, tpl: dict) -> str:
    return (tpl.get("module") or module or "").lower()
