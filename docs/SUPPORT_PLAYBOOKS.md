# Greena Support Playbooks

Step-by-step responses to common tickets. Each play states: **signal → diagnose
→ resolve → escalate**. Never enter a user's password or payment details; use
resets and grants. Capture the `request_id` (returned in `X-Request-ID`) for any
API-level issue.

## P1 — "I can't log in"
1. **Diagnose**: Does the account exist? Is the password being reset-looped? (Email verification is config-gated OFF in V1, so unverified email is *not* the cause.)
2. **Resolve**: Send them through **Forgot password** on the login screen. Confirm the reset email provider is up (`EMAIL_PROVIDER`).
3. **Escalate**: repeated failures with correct credentials → check rate limiting (429) and Sentry for the request_id.

## P2 — "I paid but my subscription isn't active"
1. **Diagnose**: Find the org's row in `payment_transactions` by reference. Check Paystack dashboard status for that reference.
2. **Resolve**:
   - Paystack shows **success**, subscription inactive → run owner-only `GET /api/v1/billing/verify/{reference}` — it re-verifies against Paystack and activates **idempotently**.
   - Paystack shows **abandoned/failed** → no payment completed; ask them to retry checkout.
3. **Escalate**: success on Paystack but verify still won't activate → capture the reference + response and escalate to engineering (possible metadata mismatch — activation checks amount/currency/metadata against the stored plan).

## P3 — "My referral discount / reward didn't work"
1. **Diagnose**: Referral rules — code entered **within 48h** of org creation, org had **no prior referral** (immutable once set), and discount applies to the **first** Starter payment only.
2. **Resolve**: If within rules and unapplied, check `referrals` row (`reward_status`) and `credit_ledger`. Reward credits on the referred org's first *successful* payment — pending until then.
3. **Escalate**: rule met but no ledger entry after a confirmed first payment → engineering (the reward path is idempotent + DB-guarded; a missing entry is a real bug).

## P4 — "I think I was charged twice"
1. **Diagnose**: List `payment_transactions` for the org. Activation is idempotent (status guard + Paystack re-verify) and reward credit is DB-unique per payment.
2. **Resolve**: Reassure — duplicate webhooks cannot double-activate or double-credit. If two *distinct* Paystack charges exist, refund via Paystack dashboard (owner).

## P5 — "I hit a limit / can't add more farms/flocks/team"
1. **Diagnose**: Compare usage to the org's plan (see [ADMINISTRATOR_MANUAL.md](ADMINISTRATOR_MANUAL.md) limits table).
2. **Resolve**: Recommend the right upgrade in Billing. For a legitimate comp, an admin can grant a plan (`activation_source = admin`).

## P6 — "Old data disappeared"
1. **Diagnose**: Free plan retains **90 days** of history; paid plans retain everything.
2. **Resolve**: Explain retention; upgrade restores full history visibility (data isn't deleted, just gated).

## P7 — "ARIA isn't answering / is slow"
1. **Diagnose**: Monthly ARIA limit reached? (Free 100, Starter 2 000, etc.) Provider outage?
2. **Resolve**: Deterministic answers still work at the cap; open-ended AI resumes next cycle or on upgrade. For provider issues, ARIA fails over automatically; if persistent, rotate the AI key (owner) and redeploy.

## P8 — "The site is down / very slow"
1. **Diagnose**: `GET /health`. 503 → DB issue (see [DISASTER_RECOVERY.md](DISASTER_RECOVERY.md)). Slow first request → free-tier **cold start** (>60s after idle).
2. **Resolve**: Warm via `/health`; for real load slowness, the fix is a paid tier (measured ceiling ~8–10 rps). Frontend broken → `vercel rollback`.

## P9 — Suspected security issue (leak, breach, abuse)
1. **Freeze** the affected action; **do not** delete evidence.
2. Capture rows/logs/`request_id`; check `audit_logs`.
3. Rotate any implicated secret immediately (owner).
4. Escalate to owner + engineering. Never weaken auth/isolation to "unblock".

## Golden rules
- Never ask for or enter a user's password or card details.
- Prefer platform tools (resets, admin grants, verify endpoint) over raw DB edits.
- Every money question: check `payment_transactions` + Paystack, both.
- Log the `request_id`; it ties the ticket to the exact server event.
