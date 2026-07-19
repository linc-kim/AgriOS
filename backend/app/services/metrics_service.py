"""
Greena — Metrics Service (Module 11).

An in-process metrics registry plus a Prometheus text exposition endpoint.

Deliberately dependency-free rather than pulling in prometheus_client: V1 runs
a single process per instance (AD-13 — APScheduler embedded in FastAPI), the
metric set is small and known, and the text format is stable and trivial to
emit. If Greena moves to multi-process workers this must move to a shared
store, since these counters are per-process.

Request metrics are recorded by MetricsMiddleware; business metrics are read
from the database on scrape.
"""

import threading
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings

# Latency histogram buckets in seconds, chosen around the shape of this API:
# most reads are single-digit ms, report generation runs into hundreds of ms,
# and exports are the only thing expected past a second.
LATENCY_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)


class MetricsRegistry:
    """Thread-safe in-process counters. Reset only by a restart."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.started_at = time.time()
        # (method, path_template, status) -> count
        self._requests: dict[tuple[str, str, int], int] = defaultdict(int)
        # (method, path_template) -> per-bucket observation counts.
        # Slot i holds observations falling in bucket i only (NOT cumulative);
        # the final slot is the overflow for anything above the last edge.
        # Prometheus wants cumulative counts, so render_prometheus sums these —
        # storing them cumulatively too would double-count every observation.
        self._latency: dict[tuple[str, str], list[int]] = defaultdict(
            lambda: [0] * (len(LATENCY_BUCKETS) + 1)
        )
        self._latency_sum: dict[tuple[str, str], float] = defaultdict(float)
        self._exceptions: dict[str, int] = defaultdict(int)
        self._events: dict[str, int] = defaultdict(int)

    def record_request(self, method: str, path: str, status: int, seconds: float) -> None:
        key = (method, path)
        with self._lock:
            self._requests[(method, path, status)] += 1
            self._latency_sum[key] += seconds
            buckets = self._latency[key]
            for i, edge in enumerate(LATENCY_BUCKETS):
                if seconds <= edge:
                    buckets[i] += 1
                    break
            else:
                buckets[-1] += 1  # slower than every defined bucket

    def record_exception(self, exc_type: str) -> None:
        with self._lock:
            self._exceptions[exc_type] += 1

    def record_event(self, name: str) -> None:
        """Count a domain event (backup_created, import_failed, …)."""
        with self._lock:
            self._events[name] += 1

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "requests": dict(self._requests),
                "latency": {k: list(v) for k, v in self._latency.items()},
                "latency_sum": dict(self._latency_sum),
                "exceptions": dict(self._exceptions),
                "events": dict(self._events),
                "uptime_seconds": time.time() - self.started_at,
            }

    def summary(self) -> dict:
        """Aggregate view for the System Status page (not Prometheus)."""
        snap = self.snapshot()
        total = sum(snap["requests"].values())
        errors = sum(c for (_, _, status), c in snap["requests"].items() if status >= 500)
        client_errors = sum(
            c for (_, _, status), c in snap["requests"].items() if 400 <= status < 500
        )
        total_latency = sum(snap["latency_sum"].values())

        by_route: list[dict] = []
        for (method, path), buckets in snap["latency"].items():
            count = sum(buckets)  # every slot, including the overflow bucket
            if not count:
                continue
            by_route.append({
                "method": method,
                "path": path,
                "count": count,
                "avg_ms": round(snap["latency_sum"][(method, path)] / count * 1000, 2),
            })
        by_route.sort(key=lambda r: r["avg_ms"], reverse=True)

        return {
            "uptime_seconds": int(snap["uptime_seconds"]),
            "total_requests": total,
            "server_errors": errors,
            "client_errors": client_errors,
            "error_rate": round(errors / total, 4) if total else 0.0,
            "avg_latency_ms": round(total_latency / total * 1000, 2) if total else 0.0,
            "exceptions": snap["exceptions"],
            "events": snap["events"],
            "slowest_routes": by_route[:10],
        }


registry = MetricsRegistry()


# ── Prometheus exposition ─────────────────────────────────────────────────────

def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _lines_for_counter(name: str, help_text: str, samples: list[tuple[dict, float]]) -> list[str]:
    out = [f"# HELP {name} {help_text}", f"# TYPE {name} counter"]
    for labels, value in samples:
        if labels:
            rendered = ",".join(f'{k}="{_escape(str(v))}"' for k, v in labels.items())
            out.append(f"{name}{{{rendered}}} {value}")
        else:
            out.append(f"{name} {value}")
    return out


def render_prometheus(business: dict | None = None) -> str:
    """
    Render the registry (and optional business gauges) as Prometheus text v0.0.4.

    Metric names follow the convention: unit-suffixed, _total on counters.
    """
    snap = registry.snapshot()
    lines: list[str] = []

    lines.extend(_lines_for_counter(
        "greena_http_requests_total",
        "Total HTTP requests by method, path and status.",
        [
            ({"method": m, "path": p, "status": s}, c)
            for (m, p, s), c in sorted(snap["requests"].items())
        ],
    ))

    # Latency histogram.
    lines.append("# HELP greena_http_request_duration_seconds HTTP request latency.")
    lines.append("# TYPE greena_http_request_duration_seconds histogram")
    for (method, path), buckets in sorted(snap["latency"].items()):
        labels = f'method="{_escape(method)}",path="{_escape(path)}"'
        cumulative = 0
        for i, edge in enumerate(LATENCY_BUCKETS):
            cumulative += buckets[i]
            lines.append(
                f'greena_http_request_duration_seconds_bucket{{{labels},le="{edge}"}} {cumulative}'
            )
        # +Inf is every observation, including the overflow slot.
        total = cumulative + buckets[-1]
        lines.append(f'greena_http_request_duration_seconds_bucket{{{labels},le="+Inf"}} {total}')
        lines.append(f'greena_http_request_duration_seconds_sum{{{labels}}} {snap["latency_sum"][(method, path)]:.6f}')
        lines.append(f'greena_http_request_duration_seconds_count{{{labels}}} {total}')

    lines.extend(_lines_for_counter(
        "greena_exceptions_total",
        "Unhandled exceptions by type.",
        [({"type": t}, c) for t, c in sorted(snap["exceptions"].items())],
    ))

    lines.extend(_lines_for_counter(
        "greena_events_total",
        "Domain events (backups, imports, exports, restores).",
        [({"event": e}, c) for e, c in sorted(snap["events"].items())],
    ))

    lines.append("# HELP greena_uptime_seconds Process uptime.")
    lines.append("# TYPE greena_uptime_seconds gauge")
    lines.append(f"greena_uptime_seconds {snap['uptime_seconds']:.1f}")

    lines.append("# HELP greena_build_info Build metadata; always 1.")
    lines.append("# TYPE greena_build_info gauge")
    lines.append(
        f'greena_build_info{{version="{_escape(settings.VERSION)}",'
        f'environment="{_escape(settings.ENVIRONMENT)}"}} 1'
    )

    if business:
        lines.append("# HELP greena_entities Current row counts of core entities.")
        lines.append("# TYPE greena_entities gauge")
        for entity, count in sorted(business.get("entities", {}).items()):
            lines.append(f'greena_entities{{entity="{_escape(entity)}"}} {count}')

        lines.append("# HELP greena_active_users_24h Users seen in the last 24 hours.")
        lines.append("# TYPE greena_active_users_24h gauge")
        lines.append(f"greena_active_users_24h {business.get('active_users_24h', 0)}")

    return "\n".join(lines) + "\n"


# ── Business metrics ──────────────────────────────────────────────────────────

async def collect_business_metrics(db: AsyncSession) -> dict:
    """
    Row counts and activity gauges scraped from the database.

    Kept to cheap aggregate counts — this runs on every Prometheus scrape, so
    it must not become a reporting query.
    """
    from app.models.auth import User
    from app.models.farm import Farm
    from app.models.flock import DailyLog, Flock
    from app.models.organization import Organization
    from app.models.production import Backup

    entities: dict[str, int] = {}
    for label, model in (
        ("users", User),
        ("organizations", Organization),
        ("farms", Farm),
        ("flocks", Flock),
        ("daily_logs", DailyLog),
        ("backups", Backup),
    ):
        try:
            result = await db.execute(
                select(func.count(model.id)).where(model.deleted_at.is_(None))
            )
            entities[label] = int(result.scalar() or 0)
        except Exception:
            # A metrics scrape must never fail the request because one count did.
            entities[label] = -1

    active_users = 0
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        result = await db.execute(
            select(func.count(User.id)).where(
                User.last_login_at.is_not(None),
                User.last_login_at >= cutoff,
                User.deleted_at.is_(None),
            )
        )
        active_users = int(result.scalar() or 0)
    except Exception:
        active_users = -1

    return {"entities": entities, "active_users_24h": active_users}
