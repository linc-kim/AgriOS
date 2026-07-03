# AGRIOS ROADMAP

**Read `AGRIOS_MASTER_CONTEXT.md` first.** This document uses the same phase numbering as `ARIA_AI.md` and `KNOWN_TECHNICAL_DEBT.md`: **V1** is the current, shipped product; **Phase 2**, **Phase 3**, and **Phase 4 and beyond** describe the intended sequence of expansion. This numbering is deliberate and should not be reshuffled casually — the order reflects a considered dependency chain and a repeatedly-validated philosophy (`AGRIOS_MASTER_CONTEXT.md` Section 4.1: product before infrastructure; earn complexity, do not pre-build it), not an arbitrary wishlist.

---

## 1. The Governing Rule for This Roadmap

Nothing on this roadmap should be pulled forward into an earlier phase without explicitly checking it against the frozen decision register (`AGRIOS_MASTER_CONTEXT.md` Section 9) and the specific reasoning recorded in `PROJECT_HISTORY.md` Section 1 for why "impressive infrastructure" was previously built before the product that needed it existed, and had to be discarded. The single test worth applying before accelerating anything below: **is there a real, currently-observed farmer or business need driving this, or is it interesting to build for its own sake?** Only the former justifies moving something earlier than planned.

---

## 2. Short Term — Phase 2

Phase 2 is the first expansion past V1, and every item in it was deliberately scoped out of V1 rather than simply not thought of — see the specific reasoning for each in `AGRIOS_MASTER_CONTEXT.md` and `ARIA_AI.md` where noted.

**Authentication expansion (`AGRIOS_MASTER_CONTEXT.md` Section 6.1):**

- **SMS OTP activation.** Unlike every other item on this roadmap, this is not really "future work" in the engineering sense — the channel-agnostic authentication architecture was built specifically so that enabling SMS is a Railway environment-variable change (adding Africa's Talking credentials), not a development project (`DEPLOYMENT_GUIDE.md` Section 6.1). It is listed here only so that it is not mistaken for a larger initiative than it actually is, and as a reminder that if turning it on ever *does* require code changes, that is itself a bug to fix, not a sign the roadmap item was under-scoped.
- **Two-factor authentication.** Once a user has verified both an email and a phone number, they may enable 2FA using any two of their verified channels, choosing a preferred and a backup channel from among Email OTP and SMS OTP (`AGRIOS_MASTER_CONTEXT.md` Section 6.1). This is sequenced in Phase 2 rather than V1 because it depends on a meaningful share of users having *two* verified channels, which itself depends on SMS being active and adopted — it is a natural next step once the underlying channel infrastructure is proven in production, not before.
- **Contact preference as a first-class setting.** Promoting the existing per-user notification toggle (`SYSTEM_ARCHITECTURE.md` Section 6) from a single SMS on/off switch into a genuine "Email / SMS / Both" preference that governs disease alerts, notifications, billing reminders, and security verification uniformly. The underlying `metadata_` JSONB storage already supports this without a migration (`DATABASE_ARCHITECTURE.md` Section 12.2); the Phase 2 work is primarily the UI and the consistent application of the preference across every outbound message type, not new backend infrastructure.

**Other Phase 2 items:**

- **AI disease diagnosis (text-based symptom assessment).** ARIA gains the ability to reason about described symptoms (not yet photos) and suggest likely conditions, still bounded by the same honesty rules that govern V1 ARIA (`ARIA_AI.md` Section 9) — it must continue to defer to a real veterinarian for medical decisions, not replace one.
- **AI sell-timing advisor.** Uses accumulated flock performance and market price data to suggest an optimal sale window — a natural extension of ARIA's existing FCR/financial reasoning once enough historical data exists across flocks to make the suggestion meaningful.
- **Proactive morning briefings from ARIA**, delivered via whichever channel(s) the farmer's contact preference specifies (Email, SMS, or both — `AGRIOS_MASTER_CONTEXT.md` Section 6.1). Distinct from the existing scheduled notification types (`SYSTEM_ARCHITECTURE.md` Section 6) — this would be ARIA-authored, not template-authored, content, which is why it is deliberately gated behind Phase 2 rather than shipped in V1: it requires more confidence in ARIA's unsupervised output quality than the bounded V1 Q&A pattern does.
- **Image upload for health records and receipts.** Requires a storage pipeline; Supabase Storage is already configured in the infrastructure (seeded, not yet user-facing) specifically in anticipation of this.
- **Voice input to ARIA (Swahili speech-to-text).** Directly serves the mobile-first, low-literacy-friction design philosophy (`DESIGN_SYSTEM.md` Section 8.4) for farmers who would rather speak a question than type it.
- **PDF report export** (batch performance, P&L). One of the most frequently requested features per operational feedback; deferred from V1 purely to keep the initial build surface area small, not because it is technically difficult.
- **M-Pesa payment integration for subscription upgrades.** The single most consequential Phase 2 item from a business-viability standpoint — see Section 6 for the specific integration options already evaluated.

---

## 3. Medium Term — Phase 3

- **Authenticator app and passkey support.** Additional verified-channel types layered onto the same single-identity model established in `AGRIOS_MASTER_CONTEXT.md` Section 6.1 — implemented as more ways to prove control of an existing AGRIOS identity, never as a parallel registration system. Sequenced after Phase 2's 2FA work, since 2FA is expected to establish the preferred/backup-channel selection pattern these would plug into.
- **Third-party identity providers (Google, Apple, Microsoft).** Also additive to the single-identity model, and specifically relevant once AGRIOS has enterprise-tier or platform-staff users (`Section 4` below) who are more likely to already use organizational SSO than the primary smallholder-farmer persona (`AGRIOS_MASTER_CONTEXT.md` Section 3) is. Linking one of these providers to an existing account must follow the identical rule as every other channel: it attaches to one existing `users` row, it never creates a second one (`DATABASE_ARCHITECTURE.md` Section 12.3).
- **Full offline-first operation** — a local SQLite (or equivalent) write queue on the client with background sync to the server once connectivity returns, including real conflict-resolution logic. This is explicitly *not* V1's "offline-aware" behavior (cached reads, service-worker asset caching) — it is a materially larger engineering effort, and per `AGRIOS_MASTER_CONTEXT.md` Section 4.2, it is deliberately sequenced *after* the product has real farmers experiencing real sync pain, not before.
- **Outbreak pattern detection** — cross-farm, anonymized aggregation of health events to detect emerging regional disease patterns before they are individually visible to any single farm. This requires enough farms and enough health data volume to be statistically meaningful, which is itself a reason it cannot be pulled earlier.
- **ARIA image-based disease diagnosis** — the photo-plus-symptom assessment capability that V1 and Phase 2 both explicitly exclude (`ARIA_AI.md` Section 3). This is intentionally sequenced after Phase 2's text-based diagnosis work, so that the underlying prompt and safety-boundary patterns are already proven on the simpler text-only case first.

---

## 4. Long Term — Phase 4 and Beyond

- **ARIA autonomous action-taking ("agent mode").** ARIA moving from recommending actions to taking them on a farmer's behalf. This is the single most safety-sensitive item on the entire roadmap and must preserve every permanent ARIA boundary established in `ARIA_AI.md` Section 3 — in particular, autonomous mode must never grant ARIA the ability to independently initiate SMS outside the existing, deliberately narrow trigger system, and must never extend into medical/veterinary decision-making regardless of how capable the underlying model becomes.
- **Predictive disease risk scoring.** A natural evolution of outbreak pattern detection (Phase 3) into forward-looking risk estimates for an individual farm, rather than purely reactive alerting.
- **Multi-farm enterprise analytics.** The point at which the currently-seeded-but-inactive `enterprise_owner` role (`AGRIOS_MASTER_CONTEXT.md` Section 3, RD-02) finally gets real user-facing flows — consolidated dashboards across multiple farms, farm-vs-farm comparison views, and a distinct enterprise navigation layer sitting on top of the existing per-farm product without modifying it (`DESIGN_SYSTEM.md` Section 9.5 already specifies exactly how this layer should be built when the time comes).
- **Marketplace** (feed, vaccine, and chick supplier connections). A genuinely new business model surface, not merely a feature — it introduces transactional and trust dynamics the current platform has never had to handle, and should be treated as its own project-level initiative rather than a sprint-sized addition.
- **Farmer community and verified discussions.** A social layer, explicitly sequenced late because it is orthogonal to the operational core the entire V1–Phase 3 roadmap is built around, and because community moderation is a real, ongoing operational burden that should not be taken on before the core business is durable.
- **Vet consultation booking and payment.** A logical extension of the existing `vet_consultant` role (already active in V1 in a read-only capacity) into a full two-sided marketplace between farmers and veterinary professionals.
- **Weather integration.** Feeds directly into ARIA's insight generation (a ninth-or-later insight type layered onto the existing eight, `ARIA_AI.md` Section 7) once a reliable, cost-appropriate weather data source for the target regions is identified.
- **IoT sensor integration, drone or satellite systems, insurance or lending products.** All explicitly late-stage — each depends on AGRIOS first having enough trustworthy operational and financial history per farm (itself dependent on sustained high DAL, `AGRIOS_MASTER_CONTEXT.md` Section 5.2) to make the integration meaningful; building sensor or lending integrations before that data trust exists would be repeating the exact mistake documented in `PROJECT_HISTORY.md` Section 1.

---

## 5. Expansion Beyond Poultry — the Species Roadmap

The technical mechanism for this expansion — `species_profiles`, and the module-accent-color design pattern — already exists and is fully specified in `DATABASE_ARCHITECTURE.md` Section 4.3 and `DESIGN_SYSTEM.md` Section 9. The roadmap for *which* species come next and in what order:

| Module | Accent color | Rationale for its position in the sequence |
|---|---|---|
| Rabbit OS | Warm Amber `#D97706` | Smallest step from poultry in farm-management complexity (similar cycle lengths, similar smallholder operator profile), making it a reasonable first proof of the extensibility model with a real, second species. |
| Dairy OS | Sky Blue `#0284C7` | A materially different operational model (milking sessions, lactation curves rather than flock-cycle batches) — deliberately sequenced after Rabbit OS so the extensibility pattern is proven on an easier case first. |
| Fish OS | Teal `#0D9488` | Aquaculture-specific concerns (pond/tank health, dissolved oxygen) introduce new environmental-monitoring needs beyond anything the poultry-derived data model anticipates. |
| Crop OS | Earth Brown `#92400E` | The largest conceptual departure from the livestock-batch model underlying the current schema (fields and growth stages rather than flocks and daily logs) — sequenced last among the currently-named modules for that reason. |

**The test for readiness to activate any of these:** per `AGRIOS_MASTER_CONTEXT.md` Section 8, activating a new species must require flipping `is_active = TRUE` on its `species_profiles` row and adding new, purely additive tables — never modifying `flocks`, `daily_logs`, or any other existing operational table. If preparing to activate a new species reveals that the existing schema *must* change to accommodate it, that is a signal to pause and revisit the extensibility model itself before proceeding, not a signal to make an exception "just this once."

---

## 6. Payments — the Path to Automated Billing

V1 ships with entirely manual payment tracking, by deliberate design (`AGRIOS_MASTER_CONTEXT.md` Section 5.1). The evaluated options for automating this in Phase 2, in the order they were assessed:

| Option | Assessment |
|---|---|
| M-Pesa Daraja API | Safaricom's official API; enables true automatic payment confirmation. Requires a registered Safaricom business account (Paybill or Buy Goods). Estimated integration effort: roughly two weeks of developer time. Transaction fees only, no fixed monthly cost. This is the most Kenya-native option and the most likely default choice. |
| Pesapal | A payment aggregator handling M-Pesa, cards, and bank transfers through one integration; generally faster to stand up than a direct Daraja integration, at the cost of an aggregator's margin. |
| Flutterwave | A pan-African payment platform with solid documentation and no fixed monthly fee (percentage-per-transaction pricing); a reasonable option if or when AGRIOS expands beyond Kenya, since it already spans multiple African markets. |
| Stripe (cards only) | Does not support M-Pesa directly, so it is relevant only for a diaspora or NGO-client payment path, not for the core Kenyan smallholder farmer base — not a primary option for V1's actual users. |

Regardless of which is chosen, the manual-tracking database fields (subscription status, plan, end date) already in place from V1 are expected to remain the source of truth that an automated integration writes into — this is intentionally an additive change to the existing subscription model, not a replacement of it.

---

## 7. Analytics and Enterprise — What Comes With Scale

As DAL (`AGRIOS_MASTER_CONTEXT.md` Section 5.2) is sustained at the higher rollout gates and the farmer base grows, two categories of work become relevant that are explicitly not V1 concerns: **deeper platform analytics** (cohort retention analysis, churn prediction feeding back into product prioritization, and eventually predictive signals derived from the same DAL and financial-snapshot data already being collected — no new data collection is anticipated to be required, only new analysis over data the schema already captures), and **the enterprise tier** described in Section 4 above. Both are sequenced deliberately after sustained evidence of product-market fit at the individual-farmer level, consistent with the project's founding lesson (`PROJECT_HISTORY.md` Section 1) that impressive-sounding future capability is not a substitute for a working, adopted core product.

---

## 8. Internationalization — Beyond Kenya

Expanding to a second country (Uganda and Tanzania are the most frequently discussed candidates, given regional proximity and similar mobile-money-driven economies) requires, at minimum: a currency configuration layer (KES is currently hardcoded, PD-03 frozen for V1 specifically), phone-number format handling beyond the current `+254`-specific validation, and genuinely new language support beyond English/Swahili if the target country's primary languages differ. None of this is a configuration toggle — it is real engineering work touching validation logic throughout the backend and UI copy throughout the frontend, and it should be scoped as its own project once a specific expansion country is actually chosen, not built speculatively for an unspecified future market.

---

## 9. How to Use This Roadmap

When scoping any new sprint, check three things in this order: first, is the work already-shipped V1 scope, in which case it belongs in `KNOWN_TECHNICAL_DEBT.md` if incomplete, not here; second, does it appear explicitly in this roadmap, in which case build it in the phase it is assigned to, respecting the dependency reasoning given for that phase; third, if it appears nowhere in this document, treat that absence as a signal to explicitly discuss and record the decision — via the same override-and-document discipline used for any frozen decision (`AGRIOS_MASTER_CONTEXT.md` Section 9) — rather than silently building it and leaving this roadmap stale relative to what the product has actually become.
