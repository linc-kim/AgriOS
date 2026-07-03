# AGRIOS MASTER CONTEXT
## The Constitution of the Project

**Status:** Living document — the highest-authority reference in the AGRIOS documentation set.
**Audience:** Any engineer, architect, or AI coding agent who has never seen AGRIOS before and must understand it completely before writing a single line of code.
**Relationship to other documents:** Every other document in this handbook (`SYSTEM_ARCHITECTURE.md`, `DATABASE_ARCHITECTURE.md`, `DESIGN_SYSTEM.md`, `ARIA_AI.md`, `DEPLOYMENT_GUIDE.md`, `CODING_STANDARDS.md`, `PROJECT_HISTORY.md`, `KNOWN_TECHNICAL_DEBT.md`, `ROADMAP.md`) is a specialization of the philosophy laid out here. If a decision described elsewhere ever seems to contradict this document, this document wins unless it has been explicitly and formally revised.

---

## 1. What AGRIOS Is

AGRIOS is a compound of "Agriculture" and "OS" (Operating System). The name deliberately draws on the Greek root *agrios* ("of the field") and positions the product not as a farm app but as the foundational operating layer for African agricultural businesses — the same relationship iOS or Windows has to a phone or a computer. This naming choice was not cosmetic. It was made to set the ambition ceiling of the entire project: AGRIOS is meant to eventually be the substrate that many different agricultural verticals run on top of, not a single-purpose utility.

**In one sentence:** AGRIOS is the daily operating system for Kenyan poultry farmers — it tracks their birds, monitors their money, manages their health records, and answers their questions with AI.

V1 of AGRIOS is a single, deliberately narrow product: a poultry farm management Progressive Web App (PWA) for Kenyan chicken farmers (broilers, layers, and other bird species), designed around a farmer on a mid-range Android phone with intermittent connectivity. Every architectural decision in this document set exists in service of that narrow V1 product, even where the underlying systems were built to extend far beyond it.

### 1.1 What AGRIOS actually gives a farmer, in plain terms

- A daily log: mortality, feed usage, egg production, weight checks.
- A health tracker: vaccination scheduling, vaccination history, disease alerts.
- A finance tracker: expense and revenue logging with automatic per-flock profit/loss.
- ARIA: an AI assistant that has read the farmer's real data and can answer operational questions in English or Swahili.
- A platform layer: market prices, SMS notifications, farm team management.

### 1.2 What AGRIOS deliberately does not do in V1

No payments processing, no feed ordering, no veterinary appointment booking, no true offline data entry, no native app store presence, no non-poultry species, no multi-currency support, no password-based login. Every one of these exclusions is a considered decision, not an oversight — see Section 4 for why. (Note: an earlier version of this document listed "no email-based login" here. That is no longer accurate and was a scoping assumption, not a permanent principle — see Section 6.1, which now governs authentication.)

---

## 2. The Strategic Thesis

> **Health gets the install. Profit keeps the user.**

This sentence is the single most important piece of product reasoning in the entire project, and it should govern every prioritization decision an engineer or product person makes when scope is ambiguous.

**Why this framing exists:** A farmer's motivation to *install* something new is triggered by an acute, fear-driven event — a sick bird, an unexplained death, a disease rumor in the county. Health and disease-alert features are therefore the acquisition lever: they are what gets a stranger to open the app for the first time. But acute fear is not a durable reason to open an app every day. What a farmer thinks about *every single day*, whether or not anything is wrong, is money — what did I spend, what did I earn, am I making a profit this cycle. Daily profit-and-loss visibility is therefore the retention lever.

ARIA, the AI assistant, is the layer that connects these two motivations: it takes the operational data the farmer is entering for financial reasons and turns it into insight, making the whole system feel less like bookkeeping and more like having an agronomist in your pocket. This is why ARIA is described elsewhere as "the engagement flywheel," not as a standalone feature.

**Practical implication:** if a proposed feature does not clearly serve either acquisition (health/disease) or retention (financial visibility), or strengthen the flywheel (ARIA), it should be viewed with suspicion regardless of how technically interesting it is. This is also why disease *diagnosis* (as opposed to disease *alerting*) was deliberately pushed out of V1 — see Section 4.4.

---

## 3. Target Users

AGRIOS V1 is built around a specific persona, and every design decision in `DESIGN_SYSTEM.md` and every API design decision in `SYSTEM_ARCHITECTURE.md` should be checked against this persona before being accepted.

**Primary persona:** A smallholder or semi-commercial Kenyan poultry farmer. They own a mid-range Android phone, often with a cracked screen. They operate on 3G more often than 4G. They may be reading the screen outdoors, in direct sunlight, at 6am or in the evening after physical farm labor. They are literate but time-poor; they will not read a paragraph if a number and a short sentence would do. Many think in phone numbers rather than email addresses, and phone-based identity remains the most natural verification method for a large share of this population — but connectivity in the field is uneven in both directions: some farmers have data but unreliable SMS delivery, others have SMS but limited data. AGRIOS's authentication system is deliberately built to serve either reality rather than assuming one (see `SYSTEM_ARCHITECTURE.md` Section 5 for the mechanics, and Section 6.1 below for the identity philosophy this persona reasoning produced).

**Secondary personas, all scoped beneath the primary farm relationship:**
- **Farm manager** — hired help who runs day-to-day operations on behalf of an owner, with almost all of the owner's operational permissions but without farm/member administration rights.
- **Vet consultant** — an external veterinary professional given read-only access to a single farm's health data. This role exists specifically because Gate 3 of the MVP rollout (100 farmers) requires at least one vet-organization partnership as a trust signal; it is not a hypothetical future role.
- **Farm worker** — daily labor who submits operational logs (mortality, feed, weigh-ins) but cannot see or touch financial data.
- **Viewer** — an investor, bank, or auditor role with read-only access, used for exactly the kind of due-diligence and lending conversations that matter to a business trying to prove it has real operational data behind it.

**Platform-side personas, not farmer-facing:**
- **super_admin** — the founder/engineer. The only role that can promote another account to admin, and this is only possible via direct database access, never through a UI (see Section 6.4 for why this is a deliberate friction point, not a missing feature).
- **platform_admin** — support staff. Seeded into the role system from the start so that hiring a second admin later requires zero schema change, but has no V1 user-facing flows because there is no V1 support team yet.
- **enterprise_owner** — reserved for a future multi-farm business tier. Seeded, permissioned, but entirely inactive in V1 — see `ROADMAP.md`.

Understanding this persona ladder matters because it explains a recurring architectural pattern: AGRIOS frequently builds the full permission and data model for a future capability (enterprise accounts, platform admin staff, new species) at the same time it ships a much narrower V1 experience. This is a deliberate strategy, not scope creep — see Section 5.3.

---

## 4. Guiding Product Philosophy

### 4.1 Product before infrastructure

This principle exists because of a real, costly early mistake — documented in full in `PROJECT_HISTORY.md`. In the earliest phase of the project, an enormous amount of effort went into infrastructure-sounding artifacts — WireGuard mesh configuration, Kubernetes manifests, an "edge-node" offline-sync simulation, a chaos-testing harness — none of which were connected to a real farmer-facing feature, and several of which were not even valid, parseable files. An audit at that stage concluded, bluntly, that the codebase did not yet exist as a product: zero of five defined MVP features were built, while the git history described an elaborate distributed system that did not function.

The lesson that came out of that audit became a standing rule: **build what a farmer touches first, build what operations staff manage second, and do not build infrastructure that a real user's real behavior has not yet demanded.** WireGuard tunnels and Kubernetes manifests are meaningless before farmers are using the app. This is why AGRIOS V1 deliberately runs as a monolith on Railway with an embedded scheduler (APScheduler, not Celery) rather than a distributed system, even though the team clearly has the technical ability to build distributed systems — see AD-13 in Section 9.

### 4.2 Offline-first is a real requirement — but it must be earned

Kenyan connectivity gaps are real and the long-term architecture (a local write queue synced to the cloud when connectivity returns) is the correct eventual answer. But V1 deliberately ships only *offline-aware* behavior — cached data remains visible when offline, a banner communicates connection state, a service worker caches static assets — and explicitly does not attempt local write queuing or conflict resolution. That full offline-first behavior is Phase 3 scope, not V1 scope. The reasoning: building conflict-resolution logic for a write queue before you have farmers who are actually experiencing sync failures is solving an imagined problem at the cost of the real, immediate one (get farmers logging data at all).

### 4.3 Mobile-first API and UI design, without exception

Every endpoint is designed assuming a 3G connection, a small screen, and a farmer who may switch between English and Swahili mid-session. This is why the home dashboard is powered by a single summary endpoint built with SQL CTEs rather than several chatty round trips (target: all dashboard zones loaded in under two seconds on 3G, with no N+1 queries) — see `SYSTEM_ARCHITECTURE.md`.

### 4.4 Disease *alerting* is V1. Disease *diagnosis* is explicitly not

This is one of the most consequential scope decisions in the whole project and it is worth stating the reasoning plainly, because it will be tempting for a future engineer or AI agent to think of these two capabilities as adjacent and equally shippable. They are not treated as equivalent, for two reasons. First, diagnosis without image analysis is unreliable and, in a health context, unreliability has real consequences for someone's livelihood — a wrong diagnosis can lead a farmer to cull a healthy flock or fail to treat a sick one. Second, image-based diagnosis requires an upload pipeline, storage, and a materially different AI integration than the bounded, text-only Q&A ARIA does in V1. Disease diagnosis is Phase 2 (text symptom assessment) and Phase 3 (photo-based assessment) scope. ARIA in V1 is contractually forbidden — at the system-prompt level, not merely by convention — from giving veterinary medical advice or inventing a diagnosis. See `ARIA_AI.md` Section on Boundaries for the exact mechanism.

### 4.5 Monolith first, services later

One FastAPI application, one PostgreSQL database, one deployment. This is survivable at V1 scale and is explicitly preferred over microservices until real traffic demands otherwise. The `ops_manual` and scaling documentation define concrete signals for when to reconsider this (Railway CPU/memory pressure, background-job execution time crossing 60 seconds, 5,000+ farmers), but until those signals appear, splitting services is considered premature complexity, not sophistication.

---

## 5. Business Philosophy

### 5.1 Manual payments in V1 are a deliberate simplification, not a gap

AGRIOS V1 has no integrated payment gateway. Subscription status (`active`, `trial`, `expired`, `suspended`, `banned`) is tracked in the database and enforced by the API, but money changes hands over M-Pesa outside the system, and the founder manually updates each farmer's subscription record after verifying payment. This was chosen deliberately so that V1 stays simple and every payment can be manually verified while the business is small enough for that to be tractable. The intended evolution path (M-Pesa Daraja API, or an aggregator like Pesapal or Flutterwave) is fully specified in `ROADMAP.md`, but is explicitly Phase 2 — building automated payment reconciliation before there is a paying customer base to reconcile is solving a problem the business does not have yet.

### 5.2 Revenue is not the north star metric — Daily Active Loggers (DAL) is

The one MVP success metric that governs the whole V1 build is **Daily Active Loggers (DAL)** — the percentage of active farms that log at least one daily operational record on any given day. This was chosen over monthly active users, daily active users, AI query volume, or revenue, and the reasoning for rejecting each alternative matters:

- **Not MAU/DAU** — a farmer can open the app every day without ever adding data. Opening the app is not value; it is not even a proxy for value.
- **Not revenue** — revenue requires the M-Pesa integration that is explicitly Phase 2 scope, so using it as a V1 gate would be measuring something the product cannot yet produce.
- **Not AI query volume** — ARIA has nothing meaningful to reason over if daily logging is not happening; AI usage is downstream of logging, not a leading indicator.
- **Not signups** — creating an account is not using the product.

Daily logging is the one behavior that unlocks everything else: FCR data, financial snapshots, mortality trends, and ARIA context all depend on it. A farm that logs consistently is a farm ARIA can actually help; a farm that does not log is, in the words of the frozen blueprint, "a dead account with good intentions." The rollout gates are staged (≥60% DAL at 5 farmers, ≥70% at 20 farmers, ≥80% at 100 farmers), and a hard trigger exists: if DAL falls below 50% for three consecutive days at any gate, feature development stops immediately and every non-logging farmer is contacted personally before any further sprint work continues. This reflects a belief that talking to a real farmer who stopped logging teaches you more than any dashboard will.

### 5.3 Why the system is over-built for roles nobody uses yet

AGRIOS seeds `enterprise_owner` and `platform_admin` roles, builds their permission matrices, and reserves database structure for them, despite neither having any V1 user-facing flow. This looks like premature abstraction unless you understand the reasoning: the cost of adding a *role* after the fact (new enum values, new permission wiring, potential data migrations for existing rows) is much higher than the cost of seeding an inactive role up front. The same logic applies to `species_profiles` (Section 8) — the cost of retrofitting multi-species support into a schema that assumed poultry-only would be a rewrite; the cost of shipping an inactive extensibility table is nearly zero. This is a case where "build it now" is cheaper than "build it later," which is the opposite of the Section 4.1 principle — the distinction is that these are structural/schema decisions with high retrofit cost, not feature/infrastructure decisions with low retrofit cost. A future engineer should apply this same test before deciding whether something belongs now or later: **what does it cost to add this after the fact, and does that cost grow over time?**

---

## 6. Security Philosophy

### 6.1 Authentication Philosophy — verified channels, not a specific technology (Permanent, Foundational)

**This subsection is itself a frozen architectural decision, on the same footing as the Frozen Decision Register in Section 9, and should be read as amending the register, not merely describing current behavior.**

AGRIOS authenticates users through **verified communication channels**, not through any single assumed technology. A channel is "verified" once the user has proven control of it by completing an OTP challenge sent to it. In V1 the supported channels are **Email OTP** and **SMS OTP**; the architecture is deliberately built so that **future Authenticator Apps and Passkeys** are additional verified-channel types added to the same model, not a redesign of it. There is still no password field anywhere in the system — every channel is verified by possession (an inbox, a phone, a device, a security key), never by a shared secret a user must remember and that a support operation must be able to reset. This removes the same categories of burden and risk the project has always targeted: no password-reset support load, and no credential-stuffing or password-reuse risk, by construction — the mechanism generalized, but the underlying reasoning is unchanged from the project's original phone-OTP-only design.

**Why this generalization exists, and why it is permanent, not a V1-specific workaround:** AGRIOS was originally designed assuming SMS OTP via Africa's Talking would be available from day one. It will not be — the V1 launch does not yet have Africa's Talking credentials configured, and Email OTP is therefore the primary authentication mechanism at launch. Rather than treating this as a temporary substitution to be undone later, the authentication system was deliberately redesigned around the principle that **AGRIOS must never assume a specific verification technology is available** — because the same reasoning that made SMS unavailable at launch (a missing third-party integration) will recur for any future channel (an API outage, a not-yet-configured credential, a country where Africa's Talking has no coverage), and because the underlying target population itself does not uniformly have reliable access to any single channel: some farmers have data connectivity but unreliable SMS delivery in their area; others have SMS but limited or expensive data. An authentication system that hard-assumes one channel is an authentication system that silently locks out whichever farmers do not have that specific channel working for them at that moment. AGRIOS should gracefully support whichever verified channel is actually available to a given user, and should be able to add or temporarily disable a channel through infrastructure configuration alone — never through a schema or code redesign.

**Account creation is channel-agnostic by identity, not by design accident:** a user may register with either an email address or a phone number. Both paths create *exactly the same kind of AGRIOS account* — there is no "email-tier account" and "phone-tier account"; the only difference between the two registration paths is which channel was used to prove the account belongs to a real, reachable person. This matters enough to restate as an absolute rule: **a user who registers with email and later also verifies a phone number (or vice versa) must never end up with two accounts.** Both verified channels belong to one AGRIOS identity. Any future implementation work that would create a second account when a second channel is added to an existing user is a bug against this principle, not an acceptable edge case.

**The V1-specific configuration state, stated plainly so it is never mistaken for an architectural limitation:** Email OTP is the primary, and at launch the only actually-functioning, verification mechanism. Phone registration remains a first-class part of the architecture — the data model, the registration flow, and the OTP mechanics are channel-agnostic already — but SMS delivery is temporarily inactive simply because Africa's Talking credentials are not yet present in the Railway environment (`DEPLOYMENT_GUIDE.md` Section 6.1). Enabling SMS OTP later is intended to require adding the Africa's Talking API key and related variables to Railway — an infrastructure configuration change — and must never require a database redesign or a rewrite of the authentication service. If a future engineer finds themselves needing to alter the `users` table shape or rewrite `AuthService` merely to "turn SMS back on," that is a signal the channel-agnostic principle has been violated somewhere and should be corrected, not worked around.

**Future two-factor verification and contact preferences follow the same channel-agnostic model, not a bolt-on:** once a user has verified both an email and a phone number, AGRIOS is intended to let them enable two-factor authentication using any two of their verified channels (Email OTP and/or SMS OTP as of this writing, with Authenticator Apps and Passkeys as future additions to the same set), configuring a preferred verification channel and a backup verification channel from among whichever they have verified. Separately, and just as importantly, a user's **contact preference** (email, SMS, or both) is intended to be a first-class profile setting that drives more than login alone — it should govern how disease alerts, operational notifications, billing reminders, and security verification messages are delivered, exactly the same way the existing SMS-notification toggle governs today's notification delivery (`SYSTEM_ARCHITECTURE.md` Section 6). Authentication channel and notification channel are conceptually the same underlying idea — "how do we reach this verified person" — and should continue to be designed as one coherent preference model, not two independent systems that happen to both mention email and SMS.

**Future third-party identity providers are additive to this same identity, never a parallel one:** Google, Apple, and Microsoft sign-in are anticipated future additions, and — like Authenticator Apps and Passkeys — they are designed to be linked to a user's single existing AGRIOS identity rather than treated as yet another registration path that could create a duplicate account. The test for whether a future authentication feature has been built correctly is always the same: does this user still have exactly one AGRIOS identity, with one or more verified channels hanging off it, regardless of how many different ways they can prove who they are?

### 6.2 Short-lived access, longer-lived refresh, and why the split exists

Access tokens (JWT) expire in 15 minutes and live only in memory on the frontend. Refresh tokens live 30 days in an httpOnly cookie and rotate on every use. The short access-token lifetime exists specifically to minimize the exposure window if a token is ever stolen from client memory (e.g. via XSS); the httpOnly cookie for the refresh token exists specifically so that JavaScript — and therefore an XSS payload — can never read it. This pairing is a deliberate defense-in-depth choice, not an arbitrary pair of numbers, and neither value should be "tuned" without re-deriving this reasoning.

### 6.3 Rate limiting exists because every OTP channel has a cost, and OTP is a spam vector regardless of channel

Maximum three OTP requests per identifier (phone number or email address) per ten minutes, maximum three wrong OTP attempts before lockout, ten-minute OTP expiry. These numbers exist for two reasons simultaneously, and both reasons apply to every channel, not just SMS: security (prevent brute-forcing a six-digit code) and cost/abuse control. SMS cost is the more visible case (Africa's Talking charges per message, and an unrestricted OTP endpoint is a trivially abusable way to run up a founder's SMS bill), but an unrestricted Email OTP endpoint is exactly as abusable as a spam or harassment vector even though its direct per-message cost is lower — an attacker who can trigger unlimited emails to an arbitrary address can use AGRIOS as a mail bomb regardless of whether SMS is even enabled. The rate-limiting rule is therefore defined once, against "the identifier used for this OTP request," and applies uniformly to whichever channel is active — it must never be quietly relaxed for email on the assumption that email abuse is a smaller problem than SMS abuse.

### 6.4 There is no UI to promote someone to admin, on purpose

Becoming `super_admin` requires a direct SQL operation against the `user_roles` table. This is treated as a deliberate security control, not a missing feature: a role that can delete farms and access platform-wide data should never be one UI click away, and forcing it through direct database access means every admin promotion leaves an operator-visible trail and requires deliberate, hard-to-automate intent.

### 6.5 Soft deletes are the only deletion — for audit and trust reasons as much as safety

Every operational table carries `deleted_at`. Data is never physically removed by an application code path. This exists for three overlapping reasons: it protects against accidental data loss, it preserves the audit trail that a bank or investor (the `viewer` role) may eventually need to trust the platform's numbers, and it means a "banned" or "suspended" farmer's history is preserved for any future legal or dispute resolution rather than destroyed as punishment — see the explicit operational guidance in `KNOWN_TECHNICAL_DEBT.md` and `DEPLOYMENT_GUIDE.md`: *never delete user data as a punishment; suspend or ban instead.*

---

## 7. Deployment Philosophy

AGRIOS deliberately runs on a "zero-ops" hosting stack — Railway for the backend, Vercel for the frontend, Supabase for PostgreSQL — chosen so that a non-developer founder can operate the business day to day without needing an infrastructure team. A `git push` to `main` is the entire deployment mechanism: Railway and Vercel both watch the repository and redeploy automatically, gated by health checks (`GET /health` polled every 10 seconds; three consecutive healthy responses before traffic cuts over; automatic rollback on failure). This blue/green behavior means farmers are never interrupted mid-update, and it means the founder — who may have zero programming background — can safely ship updates a developer produces without personally understanding the deployment mechanics, as long as they know how to read a health check. The full mechanics, including secrets management, rollback procedure, and disaster recovery, are described completely in `DEPLOYMENT_GUIDE.md`; this section exists only to record *why* the stack was chosen: minimize operational burden on a non-technical founder above almost every other consideration, including raw cost or infinite scalability.

---

## 8. Database Philosophy

The full mechanical detail lives in `DATABASE_ARCHITECTURE.md`. At the philosophy level, four decisions matter more than any others and should be treated as close to immutable:

1. **Species extensibility (`species_profiles`) is the mechanism by which AGRIOS becomes more than a poultry app without ever rewriting poultry.** Activating Rabbit OS or Dairy OS in a future version means flipping `is_active = TRUE` on a new species row and adding new, additive tables — it must never require modifying an existing table or existing API. This is the schema-level expression of the same ambition encoded in the product name itself (Section 1).
2. **Financial numbers are never computed live.** Every mutation to an expense or revenue record immediately recomputes and stores a snapshot; the API only ever reads the snapshot. This exists so that a farm with ten thousand historical records loads its P&L in milliseconds on a 3G connection, and it is treated as frozen (DB-07) specifically because the temptation to "just aggregate it in the query" reappears with almost every new report screen — resist it.
3. **Nothing is a hard delete.** See Section 6.5.
4. **A small number of tables are append-only by design** — `audit_logs`, `ai_usage_log`, `market_prices` — because they exist specifically to be trustworthy historical records. An append-only table with an UPDATE endpoint is a contradiction; if you find yourself wanting to edit a row in one of these tables, the correct action is to insert a new row, not to edit the old one.

---

## 9. The Engineering Constitution and the Frozen Decision Register

AGRIOS's architecture is governed by a set of explicitly **frozen** decisions, each carrying an ID (`AD-` for architecture, `DB-` for database, `PD-` for product, `SD-` for security, `RD-` for roles, `AR-` for ARIA). These are not casual conventions; they were locked at the start of the V1 build specifically so that sprint work could proceed without re-litigating settled questions sprint after sprint. A frozen decision may only be changed through an explicit, written override that names the decision ID, the reason for the change, and the downstream impact on anything built against it. The full register lives in `SYSTEM_ARCHITECTURE.md` and `DATABASE_ARCHITECTURE.md`; the ones every contributor should internalize immediately are:

- **AD-13**: APScheduler embedded in the FastAPI process handles all V1 background jobs. Celery/Redis is an upgrade trigger only if a background job's execution time exceeds 60 seconds — not before.
- **DB-04**: `farm_id` is present on every operational table; all data access is farm-scoped, with `disease_alerts` and `market_prices` as the only documented, deliberate exceptions (they are platform-wide by nature).
- **DB-07**: financial snapshots are computed on mutation, never aggregated live (Section 8.2).
- **DB-08 / DB-09**: `audit_logs`, `ai_usage_log`, and `market_prices` are append-only; no UPDATE or DELETE endpoint may ever be built for them (Section 8.4).
- **PD-07 / PD-08**: ARIA in V1 is read-only Q&A; disease diagnosis is Phase 2 under no circumstances (Section 4.4).
- **SD-01–SD-03**: token lifetime and storage rules (Section 6.2).

Any engineer or AI agent working on AGRIOS should treat "is there a frozen decision that governs this?" as a required check before introducing a new pattern, in the same way one would check for an existing utility function before writing a new one.

**Formal override record — PD-04 amended:** the original frozen blueprint locked PD-04 as "Phone OTP is the only registration method — no email, no Google, no Apple sign-in." This decision is **formally amended**, effective with the authentication philosophy in Section 6.1. **Reason for the change:** AGRIOS V1 will launch without Africa's Talking (SMS) credentials configured, making phone-OTP-only registration nonviable as a launch mechanism; rather than patch around this with a temporary email-login exception, the decision was generalized into a permanent, channel-agnostic identity model that also anticipates future authenticator apps, passkeys, and third-party identity providers. **Downstream impact:** registration now accepts either email or phone as the initial verified channel, both producing the same account type (Section 6.1); SMS OTP remains fully part of the architecture and is expected to activate purely through Railway environment configuration once Africa's Talking credentials exist (`DEPLOYMENT_GUIDE.md` Section 6.1); no other frozen decision in this register is affected by this amendment. PD-04 should now be read, everywhere it is referenced across this handbook or in historical source material, as superseded by Section 6.1 of this document.

---

## 10. What Must Never Change (Without Explicit Override)

This is a deliberately short, high-signal list — the decisions where a future contributor's convenience must yield to project-wide consistency:

- Authentication is channel-agnostic: identity is verified through OTP-capable communication channels (email, SMS, and future authenticator apps / passkeys / third-party identity providers), never through a remembered password. No password field should ever be introduced as a shortcut.
- A user has exactly one AGRIOS identity no matter how many verified channels or linked providers they add. Verifying a second channel (e.g. adding phone after registering with email) must never create a second account.
- Enabling or disabling a verification channel (most concretely: turning SMS OTP on once Africa's Talking credentials exist) must be achievable through infrastructure/environment configuration alone — never through a database redesign or an authentication-service rewrite.
- No hard deletes from any application code path.
- No real-time financial aggregation in an API response path.
- `species_profiles` extensibility must never require modifying an existing operational table.
- Admin role promotion must never be exposed through a UI button.
- ARIA must never be given direct database access, must never invent data it does not have, and must never issue medical diagnoses.
- The 8-role RBAC structure is not to be casually extended; a new role should be treated as a governance decision, not a code change, because roles cascade into permission matrices, UI gating, and documentation across every other file in this handbook.

---

## 11. How to Use the Rest of This Handbook

Read this document first, always. Then, depending on what you are about to do:

- Building or modifying backend/frontend systems → `SYSTEM_ARCHITECTURE.md`
- Touching the schema or writing a migration → `DATABASE_ARCHITECTURE.md`
- Building any UI → `DESIGN_SYSTEM.md`
- Touching ARIA, prompts, or AI provider logic → `ARIA_AI.md`
- Deploying, operating, or recovering the running system → `DEPLOYMENT_GUIDE.md`
- Writing code of any kind → `CODING_STANDARDS.md`
- Understanding how AGRIOS got to its current state and why certain scars exist → `PROJECT_HISTORY.md`
- Understanding what is deliberately unfinished and why it is safe to leave unfinished for now → `KNOWN_TECHNICAL_DEBT.md`
- Understanding what comes next and in what order → `ROADMAP.md`

No document in this set should be read as a replacement for this one. If a future revision of any other document appears to contradict the philosophy recorded here, treat that as a bug in the documentation, not as license to deviate.
