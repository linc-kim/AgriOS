# Greena Onboarding & Training

Onboarding flows and role-based training curricula. Grounded in the real signup →
org → farm → team flow and the 8-role model.

## Part 1 — Onboarding flows

### New farmer (self-serve)
1. **Sign up** — email + password → signed in immediately (no email verification gate in V1).
2. **Create organization** — becomes a business; auto-grants a **21-day Professional trial** + a **referral code**.
3. **Enter a referral code** (optional, within 48h) — Billing → Referral, for the KES 599 first Starter payment.
4. **Create the first farm** — name + county.
5. **Choose a module** and set up structure (houses/units → flocks/herds/batches).
6. **Invite the team** — assign roles.
7. **Log the first day** — production/feed; meet ARIA and the daily insight.
8. **Explore Billing** — see plans; upgrade any time in the trial.

**Activation milestone** (what "onboarded" means): org created, one farm, one flock/batch, first day logged, at least one teammate or a solo confirmed. Aim to reach this in the first session.

### New teammate (invited)
1. Accept the invite → set password.
2. See only the farm(s) and modules your role allows.
3. Workers: go straight to "today's tasks" and record.

### New administrator (internal)
1. Granted a platform role (`super_admin`/`platform_admin`) by an existing owner.
2. Enable 2FA. Read [ADMINISTRATOR_MANUAL.md](ADMINISTRATOR_MANUAL.md) + [SUPPORT_PLAYBOOKS.md](SUPPORT_PLAYBOOKS.md).
3. Shadow one billing grant and one support ticket before acting solo.

## Part 2 — Training curricula

### Farm Worker (30–45 min)
- Logging production, feed, weigh-ins, mortality — **at the source, in the moment**.
- Selecting the correct house/flock.
- Vaccination reminders (upcoming/overdue) and marking them done.
- Asking ARIA a simple question.
- *Competency check*: log a full day of records accurately on the right flock.

### Farm Manager (1–2 hrs)
- Everything a worker does, plus: setting up houses/flocks, health scheduling, feed & inventory, finance (expenses/revenue), automation rules, reports & exports.
- Reading dashboards and ARIA daily insights; acting on Operations Planner tasks.
- *Competency check*: stand up a new flock end-to-end and produce a weekly report.

### Farm Owner (2–3 hrs)
- All manager topics, plus: team & roles, billing (plans, trial→paid, referrals, credits), backups/exports, multi-farm.
- Understanding plan limits and when to upgrade.
- *Competency check*: invite a team with correct roles; run a checkout in test mode; share a referral.

### Administrator (half day)
- The 8-role/191-permission model; platform vs farm scope.
- Admin billing (grants/revokes/credits/lifetime), module activation, diagnostics.
- The support playbooks and the verify/idempotency mechanics.
- *Competency check*: resolve simulated P1–P4 tickets; perform an admin grant and confirm the audit entry.

### Owner/Operator (ongoing)
- The full doc set, especially [OWNER_MANUAL.md](OWNER_MANUAL.md), [OPERATIONS_MANUAL.md](OPERATIONS_MANUAL.md), [DISASTER_RECOVERY.md](DISASTER_RECOVERY.md).
- Deploy, rollback, monitor; the scaling and backup decisions.
- *Competency check*: perform a backend rollback on staging; enable a backup; read the funnel metrics.

## Part 3 — Training materials to produce (against the live UI)
- Short screen-capture videos per workflow (signup, first flock, log a day, checkout, invite team). *These need the live UI + screen capture — capture during production, not fabricated here.*
- One-page role quick-reference cards (derive from the manuals' "what you can do" tables).
- A sandbox org with seeded demo data for hands-on practice.
