"""Migration 088 — Commercial Policy: finalize the plan catalog (C1)

The production catalog. Supersedes the placeholder seed (migration 006). Prices
live ONLY here. The ``-1`` sentinel (already used for "unlimited" limits) is
reused: Enterprise carries ``price_kes = -1`` to mark it custom / not
self-serve (the checkout rejects any plan with price <= 0). Adds
``referral_first_payment_kes`` — the discounted first-payment price applied once
with a valid referral (only Starter: 999 -> 599).

Final catalog (price · farms/houses/units/ARIA/history/team):
  free        0     1/2/500/100/90d/1
  starter     999   3/20/10000/2000/inf/10        referral 599
  pro (Prof.) 1499  10/75/50000/10000/inf/30
  farm_pro    2499  50/250/250000/50000/inf/150
  enterprise  -1*   inf everything (Fair Use)     (*custom)
"""

import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "088"
down_revision = "087"
branch_labels = None
depends_on = None

_FARM_PRO_ID = uuid.UUID("00000000-0000-0000-0000-000000000004")
_ENTERPRISE_ID = uuid.UUID("00000000-0000-0000-0000-000000000005")

_FINAL = {
    "free":    dict(display_name="Free",         price_kes=0,    max_farms=1,  max_houses_per_farm=2,   max_active_flocks=500,    max_aria_queries_per_month=100,   history_days=90, max_team_members=1,   referral_first_payment_kes=None),
    "starter": dict(display_name="Starter",      price_kes=999,  max_farms=3,  max_houses_per_farm=20,  max_active_flocks=10000,  max_aria_queries_per_month=2000,  history_days=-1, max_team_members=10,  referral_first_payment_kes=599),
    "pro":     dict(display_name="Professional", price_kes=1499, max_farms=10, max_houses_per_farm=75,  max_active_flocks=50000,  max_aria_queries_per_month=10000, history_days=-1, max_team_members=30,  referral_first_payment_kes=None),
}

_ORIGINAL = {
    "free":    dict(display_name="Free",    price_kes=0,    max_farms=1, max_houses_per_farm=3,  max_active_flocks=3,  max_aria_queries_per_month=5,  history_days=90,  max_team_members=2),
    "starter": dict(display_name="Starter", price_kes=500,  max_farms=1, max_houses_per_farm=10, max_active_flocks=10, max_aria_queries_per_month=30, history_days=365, max_team_members=5),
    "pro":     dict(display_name="Pro",     price_kes=1500, max_farms=3, max_houses_per_farm=-1, max_active_flocks=-1, max_aria_queries_per_month=-1, history_days=-1,  max_team_members=20),
}

_NEW_PLANS = [
    dict(id=_FARM_PRO_ID, name="farm_pro", display_name="Farm Pro", price_kes=2499, max_farms=50, max_houses_per_farm=250, max_active_flocks=250000, max_aria_queries_per_month=50000, history_days=-1, max_team_members=150, is_active=True, referral_first_payment_kes=None),
    dict(id=_ENTERPRISE_ID, name="enterprise", display_name="Enterprise", price_kes=-1, max_farms=-1, max_houses_per_farm=-1, max_active_flocks=-1, max_aria_queries_per_month=-1, history_days=-1, max_team_members=-1, is_active=True, referral_first_payment_kes=None),
]

_UPDATE_COLS = (
    "display_name", "price_kes", "max_farms", "max_houses_per_farm",
    "max_active_flocks", "max_aria_queries_per_month", "history_days", "max_team_members",
)


def _update_plan(name: str, values: dict, include_referral: bool) -> None:
    cols = list(_UPDATE_COLS) + (["referral_first_payment_kes"] if include_referral else [])
    assignments = ", ".join(f"{c} = :{c}" for c in cols)
    params = {c: values[c] for c in cols}
    params["name"] = name
    op.execute(
        sa.text(f"UPDATE subscription_plans SET {assignments} WHERE name = :name").bindparams(**params)
    )


def upgrade() -> None:
    op.add_column(
        "subscription_plans",
        sa.Column("referral_first_payment_kes", sa.Integer, nullable=True,
                  comment="Discounted first-payment price when a referral is applied; NULL = none"),
    )
    for name, values in _FINAL.items():
        _update_plan(name, values, include_referral=True)

    plans_table = sa.table(
        "subscription_plans",
        sa.column("id", UUID(as_uuid=True)),
        sa.column("name", sa.String),
        sa.column("display_name", sa.String),
        sa.column("price_kes", sa.Integer),
        sa.column("max_farms", sa.Integer),
        sa.column("max_houses_per_farm", sa.Integer),
        sa.column("max_active_flocks", sa.Integer),
        sa.column("max_aria_queries_per_month", sa.Integer),
        sa.column("history_days", sa.Integer),
        sa.column("max_team_members", sa.Integer),
        sa.column("is_active", sa.Boolean),
        sa.column("referral_first_payment_kes", sa.Integer),
    )
    op.bulk_insert(plans_table, _NEW_PLANS)


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM subscription_plans WHERE name IN ('farm_pro', 'enterprise')"))
    for name, values in _ORIGINAL.items():
        _update_plan(name, values, include_referral=False)
    op.drop_column("subscription_plans", "referral_first_payment_kes")
