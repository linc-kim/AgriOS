"""
AGRIOS — Finance Module Unit Tests
Schema validation only — no database required.

Tests:
  TestExpenseCategoryCreate   (6 tests)
  TestExpenseCreate           (8 tests)
  TestExpenseUpdate           (6 tests)
  TestRevenueRecordCreate     (9 tests)
  TestRevenueRecordUpdate     (4 tests)
  TestCalculatorInputs        (7 tests)
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.finance import (
    BreakEvenInput,
    ExpenseCategoryCreate,
    ExpenseCreate,
    ExpenseUpdate,
    FCRCalculatorInput,
    FeedNeedsInput,
    ProfitProjectionInput,
    RevenueRecordCreate,
    RevenueRecordUpdate,
)


# ── ExpenseCategoryCreate ─────────────────────────────────────────────────────

class TestExpenseCategoryCreate:
    """Covers ExpenseCategoryCreate schema validation."""

    def test_valid_minimal(self):
        """Minimum required fields pass."""
        cat = ExpenseCategoryCreate(name="Custom Feed", slug="custom_feed")
        assert cat.name == "Custom Feed"
        assert cat.slug == "custom_feed"
        assert cat.color is None
        assert cat.icon is None

    def test_valid_with_all_fields(self):
        """All fields populated."""
        cat = ExpenseCategoryCreate(
            name="Vaccines",
            slug="vaccines_custom",
            icon="💉",
            color="#FF5733",
        )
        assert cat.color == "#FF5733"
        assert cat.icon == "💉"

    def test_slug_invalid_uppercase(self):
        """Slug with uppercase letters must fail."""
        with pytest.raises(ValidationError) as exc_info:
            ExpenseCategoryCreate(name="Feed", slug="Custom_Feed")
        assert "slug" in str(exc_info.value).lower() or "pattern" in str(exc_info.value).lower()

    def test_slug_invalid_spaces(self):
        """Slug with spaces must fail."""
        with pytest.raises(ValidationError):
            ExpenseCategoryCreate(name="Feed", slug="my feed cost")

    def test_slug_invalid_hyphens(self):
        """Slug with hyphens must fail (underscores only)."""
        with pytest.raises(ValidationError):
            ExpenseCategoryCreate(name="Feed", slug="my-feed-cost")

    def test_color_invalid_format(self):
        """Color not in #RRGGBB hex format must fail."""
        with pytest.raises(ValidationError):
            ExpenseCategoryCreate(name="Feed", slug="feed", color="red")


# ── ExpenseCreate ─────────────────────────────────────────────────────────────

class TestExpenseCreate:
    """Covers ExpenseCreate schema validation."""

    def _valid_payload(self, **overrides):
        base = dict(
            category_id="00000000-0000-0000-0000-000000000001",
            amount=Decimal("5000.00"),
            description="Layer feed restock",
            expense_date=date.today(),
            payment_method="mpesa",
        )
        base.update(overrides)
        return base

    def test_valid_minimal(self):
        """Minimum required fields pass."""
        exp = ExpenseCreate(**self._valid_payload())
        assert exp.amount == Decimal("5000.00")
        assert exp.payment_method == "mpesa"

    def test_valid_with_quantity_and_unit(self):
        """Quantity + unit accepted alongside amount."""
        exp = ExpenseCreate(
            **self._valid_payload(
                quantity=Decimal("50.000"),
                unit="kg",
                supplier="Unga Feeds Ltd",
            )
        )
        assert exp.quantity == Decimal("50.000")
        assert exp.unit == "kg"

    def test_future_expense_date_rejected(self):
        """Expense date in the future must fail."""
        with pytest.raises(ValidationError) as exc_info:
            ExpenseCreate(**self._valid_payload(expense_date=date.today() + timedelta(days=1)))
        assert "future" in str(exc_info.value).lower() or "expense_date" in str(exc_info.value).lower()

    def test_zero_amount_rejected(self):
        """Amount of 0 must fail."""
        with pytest.raises(ValidationError) as exc_info:
            ExpenseCreate(**self._valid_payload(amount=Decimal("0.00")))
        assert "amount" in str(exc_info.value).lower()

    def test_negative_amount_rejected(self):
        """Negative amount must fail."""
        with pytest.raises(ValidationError):
            ExpenseCreate(**self._valid_payload(amount=Decimal("-100.00")))

    def test_today_date_accepted(self):
        """Today's date is valid."""
        exp = ExpenseCreate(**self._valid_payload(expense_date=date.today()))
        assert exp.expense_date == date.today()

    def test_past_date_accepted(self):
        """Past dates are valid."""
        exp = ExpenseCreate(**self._valid_payload(expense_date=date.today() - timedelta(days=30)))
        assert exp.expense_date < date.today()

    def test_optional_flock_id_accepted(self):
        """flock_id is optional — None and UUID both accepted."""
        exp_no_flock = ExpenseCreate(**self._valid_payload(flock_id=None))
        assert exp_no_flock.flock_id is None

        exp_with_flock = ExpenseCreate(
            **self._valid_payload(flock_id="00000000-0000-0000-0000-000000000099")
        )
        assert exp_with_flock.flock_id is not None


# ── ExpenseUpdate ─────────────────────────────────────────────────────────────

class TestExpenseUpdate:
    """Covers ExpenseUpdate schema validation — requires correction_reason."""

    def test_valid_with_amount_update(self):
        """Updating amount with a valid correction_reason."""
        upd = ExpenseUpdate(
            amount=Decimal("6500.00"),
            correction_reason="Entered wrong amount initially",
        )
        assert upd.amount == Decimal("6500.00")
        assert upd.correction_reason == "Entered wrong amount initially"

    def test_valid_with_notes_update(self):
        """Updating only notes with a reason."""
        upd = ExpenseUpdate(
            notes="Correct supplier is Unga Ltd",
            correction_reason="Wrong note recorded",
        )
        assert upd.notes == "Correct supplier is Unga Ltd"

    def test_correction_reason_required(self):
        """correction_reason is required even with a valid field update."""
        with pytest.raises(ValidationError) as exc_info:
            ExpenseUpdate(amount=Decimal("1000.00"))
        assert "correction_reason" in str(exc_info.value).lower()

    def test_correction_reason_too_short(self):
        """correction_reason shorter than 5 chars must fail."""
        with pytest.raises(ValidationError):
            ExpenseUpdate(amount=Decimal("1000.00"), correction_reason="fix")

    def test_correction_reason_too_long(self):
        """correction_reason longer than 500 chars must fail."""
        with pytest.raises(ValidationError):
            ExpenseUpdate(
                amount=Decimal("1000.00"),
                correction_reason="x" * 501,
            )

    def test_no_update_fields_rejected(self):
        """Providing only correction_reason with no actual field to update must fail."""
        with pytest.raises(ValidationError) as exc_info:
            ExpenseUpdate(correction_reason="I just wanted to add a reason")
        assert "at least one" in str(exc_info.value).lower() or "field" in str(exc_info.value).lower()


# ── RevenueRecordCreate ───────────────────────────────────────────────────────

class TestRevenueRecordCreate:
    """Covers RevenueRecordCreate schema validation, including type-specific rules."""

    _FLOCK_ID = "00000000-0000-0000-0000-000000000002"

    def test_valid_egg_sale_with_eggs_count(self):
        """Eggs sale with eggs_count passes."""
        rec = RevenueRecordCreate(
            flock_id=self._FLOCK_ID,
            revenue_type="eggs",
            amount=Decimal("12000.00"),
            revenue_date=date.today(),
            eggs_count=360,
        )
        assert rec.revenue_type == "eggs"
        assert rec.eggs_count == 360

    def test_valid_egg_sale_with_trays_count(self):
        """Eggs sale with trays_count (without eggs_count) passes."""
        rec = RevenueRecordCreate(
            flock_id=self._FLOCK_ID,
            revenue_type="eggs",
            amount=Decimal("3600.00"),
            revenue_date=date.today(),
            trays_count=12,
        )
        assert rec.trays_count == 12

    def test_egg_sale_missing_eggs_and_trays_rejected(self):
        """Eggs sale without eggs_count OR trays_count must fail."""
        with pytest.raises(ValidationError) as exc_info:
            RevenueRecordCreate(
                flock_id=self._FLOCK_ID,
                revenue_type="eggs",
                amount=Decimal("3600.00"),
                revenue_date=date.today(),
            )
        assert "eggs" in str(exc_info.value).lower() or "trays" in str(exc_info.value).lower()

    def test_valid_bird_sale(self):
        """Bird sale with birds_sold passes."""
        rec = RevenueRecordCreate(
            flock_id=self._FLOCK_ID,
            revenue_type="birds",
            amount=Decimal("45000.00"),
            revenue_date=date.today(),
            birds_sold=100,
            avg_weight_kg=Decimal("2.100"),
        )
        assert rec.birds_sold == 100
        assert rec.avg_weight_kg == Decimal("2.100")

    def test_bird_sale_missing_birds_sold_rejected(self):
        """Bird sale without birds_sold must fail."""
        with pytest.raises(ValidationError) as exc_info:
            RevenueRecordCreate(
                flock_id=self._FLOCK_ID,
                revenue_type="birds",
                amount=Decimal("45000.00"),
                revenue_date=date.today(),
            )
        assert "birds_sold" in str(exc_info.value).lower()

    def test_valid_manure_sale(self):
        """Manure sale with quantity + unit passes."""
        rec = RevenueRecordCreate(
            flock_id=self._FLOCK_ID,
            revenue_type="manure",
            amount=Decimal("2000.00"),
            revenue_date=date.today(),
            quantity=Decimal("5.000"),
            unit="tonnes",
        )
        assert rec.revenue_type == "manure"

    def test_valid_other_revenue(self):
        """Other type passes without type-specific fields."""
        rec = RevenueRecordCreate(
            flock_id=self._FLOCK_ID,
            revenue_type="other",
            amount=Decimal("500.00"),
            revenue_date=date.today(),
        )
        assert rec.revenue_type == "other"

    def test_invalid_revenue_type_rejected(self):
        """Unknown revenue_type must fail."""
        with pytest.raises(ValidationError):
            RevenueRecordCreate(
                flock_id=self._FLOCK_ID,
                revenue_type="honey",
                amount=Decimal("1000.00"),
                revenue_date=date.today(),
            )

    def test_flock_id_required(self):
        """flock_id is required for revenue records."""
        with pytest.raises(ValidationError) as exc_info:
            RevenueRecordCreate(
                revenue_type="other",
                amount=Decimal("500.00"),
                revenue_date=date.today(),
            )
        assert "flock_id" in str(exc_info.value).lower()


# ── RevenueRecordUpdate ───────────────────────────────────────────────────────

class TestRevenueRecordUpdate:
    """Covers RevenueRecordUpdate — correction_reason required."""

    def test_valid_amount_correction(self):
        """Updating amount with a reason."""
        from app.schemas.finance import RevenueRecordUpdate
        upd = RevenueRecordUpdate(
            amount=Decimal("14000.00"),
            correction_reason="Miskeyed the sale amount",
        )
        assert upd.amount == Decimal("14000.00")

    def test_correction_reason_required(self):
        """correction_reason missing must fail."""
        from app.schemas.finance import RevenueRecordUpdate
        with pytest.raises(ValidationError):
            RevenueRecordUpdate(amount=Decimal("14000.00"))

    def test_correction_reason_min_length(self):
        """correction_reason shorter than 5 chars must fail."""
        from app.schemas.finance import RevenueRecordUpdate
        with pytest.raises(ValidationError):
            RevenueRecordUpdate(amount=Decimal("500.00"), correction_reason="err")

    def test_no_update_fields_rejected(self):
        """Only correction_reason with no field to update must fail."""
        from app.schemas.finance import RevenueRecordUpdate
        with pytest.raises(ValidationError):
            RevenueRecordUpdate(correction_reason="I changed nothing")


# ── Calculator Inputs ─────────────────────────────────────────────────────────

class TestCalculatorInputs:
    """Covers schema validation for all four calculator inputs."""

    def test_fcr_valid(self):
        """FCR input with positive values passes."""
        inp = FCRCalculatorInput(
            total_feed_kg=Decimal("200.0"),
            total_live_weight_kg=Decimal("120.0"),
        )
        assert inp.total_feed_kg == Decimal("200.0")
        assert inp.total_live_weight_kg == Decimal("120.0")

    def test_fcr_zero_weight_rejected(self):
        """FCR with zero live weight (division by zero risk) must fail."""
        with pytest.raises(ValidationError):
            FCRCalculatorInput(
                total_feed_kg=Decimal("200.0"),
                total_live_weight_kg=Decimal("0"),
            )

    def test_profit_projection_valid(self):
        """Profit projection with all required fields passes."""
        inp = ProfitProjectionInput(
            current_bird_count=500,
            expected_close_weight_kg=Decimal("2.2"),
            expected_sale_price_per_kg=Decimal("280.00"),
            total_expenses_so_far_kes=Decimal("105000.00"),
            expected_additional_expenses_kes=Decimal("5000.00"),
            expected_mortality_pct=Decimal("3.0"),
        )
        assert inp.current_bird_count == 500
        assert inp.expected_mortality_pct == Decimal("3.0")

    def test_profit_projection_defaults_applied(self):
        """Optional additional-expense and mortality fields default sensibly."""
        inp = ProfitProjectionInput(
            current_bird_count=500,
            expected_close_weight_kg=Decimal("2.2"),
            expected_sale_price_per_kg=Decimal("280.00"),
            total_expenses_so_far_kes=Decimal("105000.00"),
        )
        assert inp.expected_additional_expenses_kes == Decimal("0")
        assert inp.expected_mortality_pct == Decimal("3")

    def test_profit_projection_mortality_out_of_range(self):
        """Mortality % over 100 must fail."""
        with pytest.raises(ValidationError):
            ProfitProjectionInput(
                current_bird_count=500,
                expected_close_weight_kg=Decimal("2.2"),
                expected_sale_price_per_kg=Decimal("280.00"),
                total_expenses_so_far_kes=Decimal("105000.00"),
                expected_mortality_pct=Decimal("105.0"),
            )

    def test_break_even_valid(self):
        """Break-even input with all required fields passes."""
        inp = BreakEvenInput(
            total_expenses_kes=Decimal("110000.00"),
            expected_birds_sold=480,
            expected_avg_weight_kg=Decimal("2.1"),
        )
        assert inp.expected_birds_sold == 480

    def test_break_even_zero_birds_rejected(self):
        """Break-even with zero expected_birds_sold must fail."""
        with pytest.raises(ValidationError):
            BreakEvenInput(
                total_expenses_kes=Decimal("110000.00"),
                expected_birds_sold=0,
                expected_avg_weight_kg=Decimal("2.1"),
            )

    def test_feed_needs_valid(self):
        """Feed needs input passes with required fields."""
        inp = FeedNeedsInput(
            current_bird_count=500,
            current_avg_weight_kg=Decimal("1.1"),
            target_weight_kg=Decimal("2.2"),
        )
        assert inp.current_bird_count == 500
        assert inp.days_remaining is None  # optional
