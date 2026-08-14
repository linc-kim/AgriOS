# Greena Administrator Manual

For `super_admin`, `platform_admin`, and billing/support administration. All
capabilities map to real permissions (`app/core/permissions.py`) and admin
endpoints (`admin_*`).

## 1. Administrative roles
| Role | Scope | Grants |
|---|---|---|
| **super_admin** | Platform | **All 191 permissions.** Module activation, admin billing, diagnostics, every org/farm. `farm_id = NULL`. |
| **platform_admin** | Platform | Platform administration subset — support views, ops, billing administration. Not farm-assignable. |

> There is no separate `billing_admin`/`support` role in V1 — those responsibilities are performed by `platform_admin` (and `super_admin`). Assign carefully: platform roles bypass farm scoping.

## 2. Billing administration
Admin billing endpoints (`admin_billing`) let an administrator manage entitlements without a payment:
- **Grant a plan** (comp / enterprise / lifetime): sets the org subscription active with `activation_source = admin` or `lifetime`; `current_period_end = NULL` means never expires.
- **Revoke / downgrade**: returns an org to Free; farms inherit the reduced entitlement.
- **Credits**: adjust an org's `credit_ledger` (source `admin_adjustment`, no payment reference — unconstrained by the reward idempotency index).
- **Lifetime grants**: `is_lifetime = true` — no expiry sweep.

Every change is written to `audit_logs`. Prefer grants over touching the DB directly.

### Plans & limits (source of truth: `subscription_plans`)
| Plan | KES/mo | Farms | Houses/farm | Active flocks | ARIA/mo | History | Team |
|---|---|---|---|---|---|---|---|
| Free | 0 | 1 | 2 | 500 | 100 | 90 d | 1 |
| Starter | 999 | 3 | 20 | 10 000 | 2 000 | ∞ | 10 |
| Professional | 1 499 | 10 | 75 | 50 000 | 10 000 | ∞ | 30 |
| Farm Pro | 2 499 | 50 | 250 | 250 000 | 50 000 | ∞ | 150 |
| Enterprise | custom | ∞ | ∞ | ∞ | ∞ | ∞ | ∞ |

`-1` in the DB = unlimited. Referral: a referred org's **first** Starter payment is **KES 599** (not 999); the referrer receives **KES 100** credit when that payment activates — once only (DB-guaranteed by the `credit_ledger` idempotency index).

## 3. Module activation
Species/platform modules can be activated platform-wide by `super_admin` (`farm.py`: "Only super_admin can activate. Activating makes module available platform-wide."). Activate a module before farms can use it.

## 4. Platform administration
`admin_platform` endpoints expose diagnostics and platform state: release history (recorded on every boot — supports rollback verification), startup validation results, and operational metrics. Use `GET /health` for liveness and the diagnostics endpoints for deeper state.

## 5. Support administration (troubleshooting)
| Symptom | Check | Action |
|---|---|---|
| "I can't log in" | User exists? Email verified? (verification is config-gated OFF in V1, so signups are usable immediately) | Reset via password-reset flow; never share/enter passwords for the user. |
| "My farm hit a limit" | Org plan vs limits table | Suggest upgrade, or admin-grant if warranted. |
| "I paid but nothing happened" | `payment_transactions` by reference; Paystack dashboard status | If Paystack shows success but subscription inactive, re-run verify `GET /api/v1/billing/verify/{reference}` (owner-only, re-verifies + activates idempotently). |
| "Referral discount didn't apply" | Referral within 48h window? Already had a referral? First payment? | Discount applies only to the first payment within 48h of org creation; immutable once set. |
| "Duplicate charge?" | `payment_transactions` for the org | Activation is idempotent (status guard + Paystack re-verify); reward credit is DB-unique per payment. Explain no double effect. |

## 6. Security & audit
- Platform roles are powerful — enable 2FA on admin accounts, limit `super_admin` to as few people as possible.
- All administrative billing actions and grants are in `audit_logs` — review periodically.
- Never weaken tenant isolation or enter a user's credentials to "help" — use grants and resets.
- Rotate any exposed secrets immediately.

## 7. Escalation
Data-loss risk, suspected breach, or a payment-integrity question → freeze the affected action, capture evidence (relevant rows, logs, `request_id`), and follow [SUPPORT_PLAYBOOKS.md](SUPPORT_PLAYBOOKS.md). For infra failures see [DISASTER_RECOVERY.md](DISASTER_RECOVERY.md).
