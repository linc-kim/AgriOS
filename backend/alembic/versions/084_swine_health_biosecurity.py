"""Migration 084 — Swine Health & Biosecurity (Module 20, Milestone 6)

Health is modelled as INDEPENDENT clinical events (Swine Doc 2 §15, Doc 3 §18), each
its own historical record linked to a pig and/or a group — never fields on the pig —
so a complete medical history is preserved. Distinct clinical types are distinct
tables (not one generic "medical record"). A ``diagnosis`` is a recorded veterinary
input only; the platform never infers it (frozen constitution §4.4).

Tables:
  swine_disease_case       — illness / injury / outbreak (group-capable via scope)
  swine_vaccination        — preventive immunisation
  swine_treatment          — medication (therapeutic | preventive) via intent
  swine_procedure          — surgical / routine husbandry procedure
  swine_observation        — exam / assessment (recorded findings, never inferred)
  swine_lab_test           — laboratory test + recorded result
  swine_mortality          — death event preserving full cause history
  swine_isolation          — historical isolation / quarantine period
  swine_biosecurity_record — operational biosecurity (visitor/vehicle/cleaning/...)
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "084"
down_revision = "083"
branch_labels = None
depends_on = None


def _base() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("metadata", JSONB, nullable=False, server_default="{}"),
    ]


def _farm() -> sa.Column:
    return sa.Column("farm_id", UUID(as_uuid=True),
                     sa.ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True)


def _pig(name="pig_id") -> sa.Column:
    return sa.Column(name, UUID(as_uuid=True),
                     sa.ForeignKey("swine_pig.id", ondelete="SET NULL"), nullable=True, index=True)


def _group() -> sa.Column:
    return sa.Column("group_id", UUID(as_uuid=True),
                     sa.ForeignKey("swine_group.id", ondelete="SET NULL"), nullable=True, index=True)


def _pen() -> sa.Column:
    return sa.Column("pen_id", UUID(as_uuid=True),
                     sa.ForeignKey("swine_pen.id", ondelete="SET NULL"), nullable=True, index=True)


def _by() -> sa.Column:
    return sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


def upgrade() -> None:
    op.create_table(
        "swine_disease_case",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        _farm(),
        sa.Column("scope", sa.String(20), nullable=False, server_default="individual",
                  comment="individual | litter | group | pen | multi_pen | farm"),
        _pig(), _group(), _pen(),
        sa.Column("litter_id", UUID(as_uuid=True),
                  sa.ForeignKey("swine_litter.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("disease_name", sa.String(200), nullable=False),
        sa.Column("pathogen", sa.String(200), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="suspected",
                  comment="suspected | confirmed | resolved | chronic | ruled_out"),
        sa.Column("severity", sa.String(20), nullable=False, server_default="mild",
                  comment="info | mild | moderate | severe | critical"),
        sa.Column("onset_date", sa.Date, nullable=True),
        sa.Column("resolved_date", sa.Date, nullable=True),
        sa.Column("affected_count", sa.Integer, nullable=False, server_default="1"),
        sa.Column("mortality_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("diagnosis", sa.Text, nullable=True,
                  comment="Recorded veterinary input ONLY — never inferred (frozen §4.4)."),
        sa.Column("reported_by", sa.String(200), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        _by(), *_base(),
    )
    op.create_index("ix_swine_disease_case_status", "swine_disease_case", ["status"])

    op.create_table(
        "swine_vaccination",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        _farm(), _pig(), _group(),
        sa.Column("vaccine_name", sa.String(200), nullable=False),
        sa.Column("disease_targeted", sa.String(200), nullable=True),
        sa.Column("dose", sa.Numeric(10, 3), nullable=True),
        sa.Column("dose_unit", sa.String(20), nullable=True),
        sa.Column("route", sa.String(20), nullable=True,
                  comment="intramuscular | subcutaneous | oral | in_feed | in_water | intranasal | topical | intravenous | other"),
        sa.Column("batch_number", sa.String(100), nullable=True),
        sa.Column("administered_on", sa.Date, nullable=False),
        sa.Column("next_due_date", sa.Date, nullable=True, index=True),
        sa.Column("administered_by", sa.String(200), nullable=True),
        sa.Column("animal_count", sa.Integer, nullable=False, server_default="1"),
        sa.Column("inventory_item_id", UUID(as_uuid=True), nullable=True),
        sa.Column("inventory_movement_id", UUID(as_uuid=True), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        _by(), *_base(),
    )

    op.create_table(
        "swine_treatment",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        _farm(), _pig(), _group(),
        sa.Column("disease_case_id", UUID(as_uuid=True),
                  sa.ForeignKey("swine_disease_case.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("intent", sa.String(20), nullable=False, server_default="therapeutic",
                  comment="therapeutic | preventive | metaphylactic"),
        sa.Column("product_name", sa.String(200), nullable=False),
        sa.Column("drug", sa.String(200), nullable=True),
        sa.Column("dose", sa.Numeric(10, 3), nullable=True),
        sa.Column("dose_unit", sa.String(20), nullable=True),
        sa.Column("route", sa.String(20), nullable=True),
        sa.Column("started_on", sa.Date, nullable=False),
        sa.Column("ended_on", sa.Date, nullable=True),
        sa.Column("duration_days", sa.Integer, nullable=True),
        sa.Column("withdrawal_until", sa.Date, nullable=True, index=True,
                  comment="Meat withdrawal end date — a recorded compliance fact."),
        sa.Column("administered_by", sa.String(200), nullable=True),
        sa.Column("outcome", sa.String(20), nullable=False, server_default="ongoing",
                  comment="recovered | improving | ongoing | no_response | died | unknown"),
        sa.Column("animal_count", sa.Integer, nullable=False, server_default="1"),
        sa.Column("inventory_item_id", UUID(as_uuid=True), nullable=True),
        sa.Column("inventory_movement_id", UUID(as_uuid=True), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        _by(), *_base(),
    )
    op.create_index("ix_swine_treatment_intent", "swine_treatment", ["intent"])

    op.create_table(
        "swine_procedure",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        _farm(), _pig(), _group(),
        sa.Column("procedure_type", sa.String(20), nullable=False, server_default="other",
                  comment="castration | tail_docking | teeth_clipping | iron_injection | ear_notching | "
                  "hernia_repair | surgery | euthanasia | other"),
        sa.Column("performed_on", sa.Date, nullable=False),
        sa.Column("performed_by", sa.String(200), nullable=True),
        sa.Column("anesthesia", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("analgesia", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("outcome", sa.String(100), nullable=True),
        sa.Column("animal_count", sa.Integer, nullable=False, server_default="1"),
        sa.Column("notes", sa.Text, nullable=True),
        _by(), *_base(),
    )

    op.create_table(
        "swine_observation",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        _farm(), _pig(), _group(),
        sa.Column("observation_type", sa.String(20), nullable=False, server_default="routine_check",
                  comment="routine_check | examination | vet_assessment | body_condition | temperature | lameness | note"),
        sa.Column("observed_on", sa.Date, nullable=False),
        sa.Column("temperature_c", sa.Numeric(4, 1), nullable=True),
        sa.Column("body_condition_score", sa.Numeric(3, 1), nullable=True),
        sa.Column("severity", sa.String(20), nullable=False, server_default="info"),
        sa.Column("findings", sa.Text, nullable=True,
                  comment="Recorded observation text — never an inferred diagnosis (§4.4)."),
        sa.Column("observed_by", sa.String(200), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        _by(), *_base(),
    )

    op.create_table(
        "swine_lab_test",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        _farm(), _pig(), _group(),
        sa.Column("disease_case_id", UUID(as_uuid=True),
                  sa.ForeignKey("swine_disease_case.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("sample_type", sa.String(100), nullable=True),
        sa.Column("test_name", sa.String(200), nullable=False),
        sa.Column("laboratory", sa.String(200), nullable=True),
        sa.Column("collected_on", sa.Date, nullable=True),
        sa.Column("result_on", sa.Date, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending",
                  comment="pending | completed | cancelled"),
        sa.Column("result", sa.String(20), nullable=False, server_default="pending",
                  comment="positive | negative | inconclusive | pending | not_recorded"),
        sa.Column("result_detail", sa.Text, nullable=True),
        sa.Column("reference", sa.String(150), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        _by(), *_base(),
    )

    op.create_table(
        "swine_mortality",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        _farm(), _pig(),
        sa.Column("litter_id", UUID(as_uuid=True),
                  sa.ForeignKey("swine_litter.id", ondelete="SET NULL"), nullable=True, index=True),
        _group(), _pen(),
        sa.Column("disease_case_id", UUID(as_uuid=True),
                  sa.ForeignKey("swine_disease_case.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("treatment_id", UUID(as_uuid=True),
                  sa.ForeignKey("swine_treatment.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("died_on", sa.Date, nullable=False),
        sa.Column("count", sa.Integer, nullable=False, server_default="1"),
        sa.Column("cause_category", sa.String(20), nullable=False, server_default="unknown",
                  comment="disease | respiratory | digestive | injury | crushing | starvation | congenital | "
                  "heat_stress | sudden_death | culled | unknown | other"),
        sa.Column("suspected_cause", sa.String(255), nullable=True),
        sa.Column("confirmed_cause", sa.String(255), nullable=True),
        sa.Column("vet_name", sa.String(200), nullable=True),
        sa.Column("disposal_method", sa.String(20), nullable=False, server_default="unknown",
                  comment="incineration | burial | composting | rendering | knackery | other | unknown"),
        sa.Column("weight_kg", sa.Numeric(8, 3), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        _by(), *_base(),
    )
    op.create_index("ix_swine_mortality_died_on", "swine_mortality", ["died_on"])

    op.create_table(
        "swine_isolation",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        _farm(), _pig(), _group(), _pen(),
        sa.Column("disease_case_id", UUID(as_uuid=True),
                  sa.ForeignKey("swine_disease_case.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("reason", sa.String(20), nullable=False, server_default="observation",
                  comment="disease | injury | quarantine_intake | observation | biosecurity | other"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active",
                  comment="active | cleared | ended"),
        sa.Column("started_on", sa.Date, nullable=False),
        sa.Column("ended_on", sa.Date, nullable=True),
        sa.Column("cleared_by", sa.String(200), nullable=True),
        sa.Column("clearance_notes", sa.Text, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        _by(), *_base(),
    )
    op.create_index("ix_swine_isolation_status", "swine_isolation", ["status"])

    op.create_table(
        "swine_biosecurity_record",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        _farm(),
        sa.Column("record_type", sa.String(30), nullable=False, server_default="inspection",
                  comment="visitor_log | vehicle_entry | equipment_disinfection | staff_sanitation | "
                  "pen_cleaning | rodent_control | deadstock_disposal | quarantine | inspection | other"),
        sa.Column("occurred_on", sa.Date, nullable=False),
        _pen(),
        sa.Column("location", sa.String(200), nullable=True),
        sa.Column("party_name", sa.String(200), nullable=True),
        sa.Column("performed_by", sa.String(200), nullable=True),
        sa.Column("product_used", sa.String(200), nullable=True),
        sa.Column("compliant", sa.Boolean, nullable=True),
        sa.Column("detail", sa.Text, nullable=True),
        sa.Column("reminder_id", UUID(as_uuid=True), nullable=True,
                  comment="Soft link to a Greena Operations reminder/task (no FK)."),
        sa.Column("notes", sa.Text, nullable=True),
        _by(), *_base(),
    )
    op.create_index("ix_swine_biosecurity_type", "swine_biosecurity_record", ["record_type"])


def downgrade() -> None:
    op.drop_table("swine_biosecurity_record")
    op.drop_table("swine_isolation")
    op.drop_table("swine_mortality")
    op.drop_table("swine_lab_test")
    op.drop_table("swine_observation")
    op.drop_table("swine_procedure")
    op.drop_table("swine_treatment")
    op.drop_table("swine_vaccination")
    op.drop_table("swine_disease_case")
