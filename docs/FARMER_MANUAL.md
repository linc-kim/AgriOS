# Greena Farmer Manual

For farm owners and managers. How to run your farm on Greena, feature by
feature. (`farm_owner` = full control; `farm_manager` = day-to-day, no member/role
changes.)

## 1. Getting started
1. **Sign up** with email + password (you're signed in immediately — no email verification needed in V1).
2. **Create your organization** — this is your business. On creation you automatically get a **21-day Professional trial** and a **referral code**.
3. **Create a farm** — give it a name and county (one of Kenya's 47). Add more farms up to your plan limit.
4. **Set up structure** — production houses/units, then flocks/herds/batches per the module you use.
5. **Invite your team** — `farm_owner` invites members and assigns roles (manager, worker, vet, viewer) up to your plan's team limit.

## 2. Your plan & limits
| Plan | Farms | Houses/farm | Active flocks | ARIA/mo | History | Team |
|---|---|---|---|---|---|---|
| Free | 1 | 2 | 500 | 100 | 90 days | 1 |
| Starter (999) | 3 | 20 | 10 000 | 2 000 | unlimited | 10 |
| Professional (1 499) | 10 | 75 | 50 000 | 10 000 | unlimited | 30 |
| Farm Pro (2 499) | 50 | 250 | 250 000 | 50 000 | unlimited | 150 |

**Tip — referral:** share your code. A friend's first Starter payment is **KES 599** instead of 999, and you get **KES 100** credit when they pay. Enter a code within **48 hours** of creating your org (Billing → Referral).

## 3. Production modules
Pick the module(s) for your animals — each is a full engine (records → health → finance → reports):
- **Poultry** — flocks, daily logs, egg/production records, weigh-ins.
- **Aviculture / Ornamental Birds** — aviaries, pairs, breeding, incubation, hatch, mutations, valuation.
- **Black Soldier Fly (BSF)** — feedstock, feeding, environment, harvest, frass, mortality.
- **Rabbit** — breeding & litters, growth/weight/feed, health, sales.
- **Small Ruminant (Goat & Sheep)** — breeding & birth, growth, health, dairy, wool, sales.
- **Swine (Pigs)** — breeding/AI/pregnancy, farrowing & litters, feed, health/biosecurity, growth, sales.
- **Fish/Aquaculture** — on the roadmap.

## 4. Everyday workflows
- **Log the day**: record eggs/production, feed given, weigh-ins, mortality. A **Daily Log Reminder** nudges you at 20:00 if nothing's logged.
- **Health**: schedule and log vaccinations; record disease events. Greena reminds you of **upcoming (08:00)** and **overdue (08:05)** vaccinations.
- **Feed & inventory**: track feed purchases, consumption, stock, suppliers, and assets.
- **Finance**: log expenses and revenue (custom categories supported); Greena computes profitability snapshots.
- **Automation**: set rules and reminders so routine actions happen on schedule.
- **Reports & exports**: generate performance reports; export to CSV/PDF. History depth follows your plan (Free = 90 days).

## 5. ARIA — your AI assistant
Ask ARIA about your farm in plain language ("how are my layers doing?", "what should I feed batch 3?"). It answers from your farm's real data, deterministic-first with AI fallback, and posts **Daily Insights** each morning (06:00). Your plan sets the monthly query limit. Full guide: [ARIA_MANUAL.md](ARIA_MANUAL.md).

## 6. Mission Control & Operations Planner
- **Operations Planner** turns your routines into concrete daily tasks (materialised 05:00), scans for compliance gaps (07:00), and optimises weekly (Mon 04:00).
- **Mission Control** is your strategic layer — goals and roadmap across farms.

## 7. Billing & subscription
- **Billing → Plans**: see plans and start a checkout (Paystack). You're redirected to pay; on success your subscription activates and farms inherit the entitlement.
- **Trial → paid**: upgrade any time during the 21-day trial; upgrading after expiry also works.
- **Payment history & credits**: view your transactions and referral credits.

## 8. Team roles (who can do what)
| Role | Can |
|---|---|
| Farm Owner | Everything on the farm incl. members, billing, backups, exports |
| Farm Manager | All day-to-day records/health/finance/feed; not member/role changes |
| Vet Consultant | Log health/vaccination; view most modules |
| Farm Worker | Log daily ops/feed/production; view assigned modules |
| Viewer | Read-only |

## 9. Troubleshooting
- **Hit a limit?** You're at your plan's cap — upgrade in Billing.
- **Can't see old data?** Free plan keeps 90 days; paid plans keep everything.
- **Payment didn't reflect?** Give it a moment (webhook); if still off, contact support with your payment reference.
