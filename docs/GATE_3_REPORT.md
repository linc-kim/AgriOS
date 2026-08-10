# GATE 3 — File-Upload, Write-Path & Data-Layer Hardening — Completion Report

**Status:** P0 implemented + verified; P1 reviewed (evidence-based). **Awaiting owner approval. NOT committed, NOT pushed.**
**Date:** 2026-08-11 · **Branch:** `phase-2-auth` (local)

## Objectives completed

### P0 (implemented + verified)
1. **File-upload hardening** — new shared validator `app/core/uploads.py`: per-category **size caps** (image/doc 8 MB, import 16 MB), **extension allowlist**, **magic-byte signature verification** (JPEG/PNG/GIF/WEBP/PDF/OOXML) and NUL-free UTF-8 checks for text (csv/txt/json), returning a **trusted MIME** so callers stop trusting the client `content_type`. Wired into all three upload sites — multimodal image, multimodal document (`ai_assistant.py`), and data import (`production.py`, which was previously an **uncapped** `file.read()`). Safe storage holds by construction (uploaded bytes are processed in-memory → Gemini/parse; never written to a served path).
2. **Write-path IDOR regression** — a non-member is denied on **all 116** runtime-discovered farm-scoped POST routes, and a denied create leaves **no state** (owner-verified before/after on `finance/categories`).
3. **Cross-organization isolation** — a user owning a farm in a different `organization_id` is refused in **both** directions (rival→workspace and workspace→rival), 403.

### P1 (reviewed — evidence-based, no premature change)
4. **Connection pooling — KEEP.** `config.py`: `DB_POOL_SIZE=5`, `DB_MAX_OVERFLOW=10`, `DB_POOL_RECYCLE=1800`s. Effective ceiling `(5+10)×workers + 1` = 31 for 2 workers, inside Supabase's 60-conn cap. Sound; recommend watching pool-utilization metrics (already emitted) under the load test.
5. **Index review — evidence captured.** Live-DB check: **208 foreign keys lack a supporting index**, but they are overwhelmingly actor/audit columns (`created_by`, `logged_by`, `administered_by`, `invited_by`, `published_by`, `recorded_by`, `corrected_by`, `assigned_by`) that are **not** query predicates. Hot FKs (`farm_id`, `user_id`, …) already carry explicit `ix_` indexes. Per Doc 3 §14 / Master Index §15 ("every index requires justification"), **bulk-indexing is the wrong move** — it would bloat writes for no read benefit. Recommendation: add targeted indexes only for the handful of genuine predicates (e.g. `expenses.category_id`) **when the load test surfaces a specific slow query**, not speculatively.
6. **Query optimization — KEEP/measure.** Hot auth path uses eager `selectinload` (N+1 avoided); a full 176-service N+1 sweep should be driven by load-test slow-query evidence (Doc 4 §92).
7. **Cache strategy — DEFER (documented).** In-process caches are correct for the single-service, 2-worker deployment; Redis/distributed cache is trigger-gated (tech-debt §8; Master Index §8–9). Implement only after the load test identifies a bottleneck.

## Files changed (delta)
- `backend/app/core/uploads.py` — **new** shared upload validator.
- `backend/app/api/v1/endpoints/ai_assistant.py` — image + document uploads validated; trusted MIME.
- `backend/app/api/v1/endpoints/production.py` — import: bounded read + validation.
- `backend/tests/unit/test_uploads.py` — **new** (12 validator unit tests).
- `backend/tests/integration/test_write_idor_and_cross_org.py` — **new** (3 tests).
- `docs/GATE_3_REPORT.md`, `docs/GREENA_STANDARDS_GAP_AUDIT.md` — this report + register updates.

## Database migrations
**None.** (Index review recommends targeted, evidence-driven additions later — not this gate.)

## Tests executed
- **Environment:** local embedded Postgres 16.14 `127.0.0.1:5433`; Python 3.12 venv; `DATABASE_URL`/`TEST_DATABASE_URL`→local; AI keys empty; `ENVIRONMENT=development`.
- `pytest tests/unit/test_uploads.py tests/integration/test_aria_assistant_api.py tests/integration/test_production_module.py` → **73 passed** in 63.9s (proves hardening doesn't break existing upload/import flows).
- `pytest tests/integration/test_write_idor_and_cross_org.py -v` → **3 passed** in 34.7s.
- **Full regression:** `pytest -q` → **1865 passed, 0 failed in 457.7s (7m37s)**.
- **Skipped tests:** none newly skipped.

## Tests passed / failed
**1865 passed, 0 failed, 0 errors.** Baseline before Gate 3 was 1850; new this gate: +15 tests (12 upload unit + 3 write/cross-org). Warnings (2127) are pre-existing `datetime.utcnow()` deprecations.

## Coverage impact
Increased: upload validation is fully unit-covered; write-path and cross-org isolation now regression-guarded (previously read-only). Line-% not captured (`-q`); CI `--cov` reports on first PR.

## Performance impact
Negligible/positive. Upload validation is O(size) header inspection. The import endpoint no longer buffers unbounded input (memory-safety improvement). No query/index/schema changes.

## Security impact
**Strongly positive.** (1) Upload content-type spoofing and unbounded-import DoS closed; magic-byte + extension allowlist + size caps enforced. (2) Write-path IDOR now proven across all 116 POST routes with a state-change assertion. (3) Cross-org isolation proven bidirectionally. No new attack surface.

## Breaking changes
**None for legitimate clients.** Uploads that previously relied on a mismatched extension/Content-Type, or a disallowed type, are now rejected (422) — intended. Existing tests (valid CSV/PDF/JSON/PNG) pass unchanged.

## Rollback strategy
`git revert` of the Gate 3 commit(s) restores prior behavior — no migrations, no data, no external state. `app/core/uploads.py` is additive; reverting the three endpoint edits removes the validation calls cleanly.

## Remaining risks / limitations
- Upload malware scanning not implemented (out of scope; low risk given in-memory, non-served processing) — future option.
- Index/query/cache tuning intentionally deferred to load-test evidence (Gate for performance).
- Deploy-workflow activation still an open owner decision.
- Gemini single-key rotation still pending (later AI gate).

## Recommendation
**Proceed.** Gate 3 P0 delivers verified upload + write-path + cross-org hardening with zero regressions and no breaking changes for valid clients; P1 is reviewed with evidence and correctly defers speculative index/cache work to the load-test gate. Recommend: approve Gate 3 + authorize commit; then schedule the **1,000-user load test** (which converts the deferred perf items into targeted, evidence-driven work) and the **Gemini key-rotation** AI gate.
