"""
ARIA NLU — parsing behaviour.

These tests are the specification for what ARIA will and will not read out of a
sentence. They matter more than most unit tests here because this parser decides
what gets written to a farmer's records: a misread quantity is a wrong number in
someone's books, and a hallucinated slot is exactly the invented farm data the
product forbids.

So there are two kinds of test below. The ordinary kind pins the happy paths.
The important kind pins the *refusals* — the cases where the right answer is to
come back with nothing and let the dialogue layer ask.
"""

from datetime import date
from decimal import Decimal

import pytest

from app.services.aria_nlu import (
    EGGS_PER_TRAY,
    Intent,
    extract_date,
    extract_flock_reference,
    extract_money,
    extract_numbers,
    extract_quantity,
    extract_vaccine,
    normalise,
    parse,
)

TODAY = date(2026, 7, 22)  # A Wednesday.


class TestNormalise:
    def test_lowercases_and_collapses_whitespace(self):
        assert normalise("  We  LOST   Three\tBirds ") == "we lost three birds"

    def test_strips_accents(self):
        assert normalise("café") == "cafe"

    def test_handles_none_and_empty(self):
        assert normalise("") == ""
        assert normalise(None) == ""


class TestNumbers:
    def test_digits(self):
        assert extract_numbers("collected 945 eggs") == [Decimal(945)]

    def test_thousands_separator(self):
        assert extract_numbers("feed cost 3,250") == [Decimal(3250)]

    def test_decimals(self):
        assert extract_numbers("average 2.4 kg") == [Decimal("2.4")]

    def test_word_numbers(self):
        assert extract_numbers("three birds died") == [Decimal(3)]

    def test_compound_word_numbers(self):
        assert extract_numbers("twenty five birds") == [Decimal(25)]

    def test_swahili_numerals(self):
        assert extract_numbers("kuku tatu walikufa") == [Decimal(3)]

    def test_preserves_order_of_appearance(self):
        assert extract_numbers("12 bags at 3,250") == [Decimal(12), Decimal(3250)]


class TestMoney:
    @pytest.mark.parametrize(
        "text,expected",
        [
            ("feed cost 3,250 each", Decimal(3250)),
            ("paid KES 45000", Decimal(45000)),
            ("ksh 1200 for transport", Decimal(1200)),
            ("sold for 15k", Decimal(15000)),
            ("3.2k per bag", Decimal(3200)),
        ],
    )
    def test_extracts_amounts(self, text, expected):
        assert extract_money(text) == expected

    def test_bare_number_is_not_money(self):
        """"12 bags" must never be read as twelve shillings."""
        assert extract_money("i bought 12 bags of feed") is None

    def test_egg_count_is_not_money(self):
        assert extract_money("collected 945 eggs") is None


class TestQuantity:
    @pytest.mark.parametrize(
        "text,amount,unit",
        [
            ("i bought 12 bags of feed", 12, "bag"),
            ("we used 150 kg", 150, "kg"),
            ("collected 20 trays", 20, "tray"),
            ("three birds died", 3, "bird"),
            ("945 eggs today", 945, "egg"),
        ],
    )
    def test_number_unit_pairs(self, text, amount, unit):
        q = extract_quantity(text)
        assert q is not None
        assert q.amount == Decimal(amount)
        assert q.unit == unit

    def test_unit_with_no_number_yields_nothing(self):
        """A bare unit must not silently become a quantity of one."""
        assert extract_quantity("i bought bags of feed") is None

    def test_distant_number_does_not_bind(self):
        """
        The number must be near its unit. In this sentence 3 belongs to the
        birds, and binding it to "bags" would record a purchase that never
        happened.
        """
        q = extract_quantity("we lost 3 birds, feed is low, i need to buy bags")
        assert q is not None
        assert q.unit == "bird"


class TestDates:
    def test_today(self):
        assert extract_date("three died today", today=TODAY)[0] == TODAY

    def test_this_morning_is_today(self):
        assert extract_date("three died this morning", today=TODAY)[0] == TODAY

    def test_yesterday(self):
        assert extract_date("collected eggs yesterday", today=TODAY)[0] == date(2026, 7, 21)

    def test_last_night_is_yesterday(self):
        assert extract_date("we lost birds last night", today=TODAY)[0] == date(2026, 7, 21)

    def test_n_days_ago(self):
        assert extract_date("vaccinated 5 days ago", today=TODAY)[0] == date(2026, 7, 17)

    def test_last_weekday(self):
        # TODAY is a Wednesday; last Monday is two days back.
        assert extract_date("vaccinated last monday", today=TODAY)[0] == date(2026, 7, 20)

    def test_iso_date(self):
        assert extract_date("on 2026-07-15 we vaccinated", today=TODAY)[0] == date(2026, 7, 15)

    def test_day_month_slash(self):
        assert extract_date("15/07 we vaccinated", today=TODAY)[0] == date(2026, 7, 15)

    def test_swahili_today_and_yesterday(self):
        assert extract_date("kuku tatu walikufa leo", today=TODAY)[0] == TODAY
        assert extract_date("walikufa jana", today=TODAY)[0] == date(2026, 7, 21)

    def test_absent_date_defaults_to_today_but_says_so(self):
        """
        Defaulting is allowed here, but never silently — recording yesterday's
        mortality against today is a real error, so the assumption is surfaced.
        """
        when, assumption = extract_date("three birds died", today=TODAY)
        assert when == TODAY
        assert assumption is not None


class TestFlockReference:
    @pytest.mark.parametrize(
        "text,expected",
        [
            ("we lost 3 birds in flock 2", "2"),
            ("vaccinated flock alpha", "alpha"),
            ("house 3 lost two birds", "3"),
            ("collected eggs from alpha", "alpha"),
        ],
    )
    def test_extracts_reference(self, text, expected):
        assert extract_flock_reference(text) == expected

    def test_no_reference_returns_none(self):
        """
        The single most important refusal. An unnamed flock must come back as
        None so the dialogue asks — guessing would attach a mortality to the
        wrong flock.
        """
        assert extract_flock_reference("three birds died today") is None


class TestVaccine:
    @pytest.mark.parametrize(
        "text,expected",
        [
            ("we vaccinated newcastle today", "Newcastle Disease (ND)"),
            ("gumboro vaccine given", "Infectious Bursal Disease (Gumboro)"),
            ("did the mareks jab", "Marek's Disease"),
            ("fowl pox done", "Fowl Pox"),
        ],
    )
    def test_canonicalises_known_vaccines(self, text, expected):
        assert extract_vaccine(text) == expected

    def test_unknown_vaccine_passes_through(self):
        """A vocabulary gap must never block recording a real vaccination."""
        assert extract_vaccine("we vaccinated zoetis rispens today") is not None


class TestIntentClassification:
    @pytest.mark.parametrize(
        "text,intent",
        [
            ("three birds died this morning", Intent.RECORD_MORTALITY),
            ("we lost two birds", Intent.RECORD_MORTALITY),
            ("kuku tatu walikufa", Intent.RECORD_MORTALITY),
            ("collected 945 eggs", Intent.RECORD_EGGS),
            ("i bought 12 bags of growers mash", Intent.RECORD_FEED_PURCHASE),
            ("we vaccinated newcastle today", Intent.RECORD_VACCINATION),
            ("we weighed flock 2", Intent.RECORD_WEIGHT),
            ("sold 480 eggs", Intent.RECORD_SALE),
        ],
    )
    def test_classifies(self, text, intent):
        assert parse(text, today=TODAY).intent is intent

    @pytest.mark.parametrize(
        "text",
        [
            "how many birds died this week?",
            "why are my layers eating less",
            "what causes coccidiosis",
            "should i vaccinate now",
        ],
    )
    def test_questions_are_not_records(self, text):
        """
        A question about mortality must never create a mortality record. This
        is the difference between an assistant and a liability.
        """
        result = parse(text, today=TODAY)
        assert result.intent is Intent.UNKNOWN
        assert not result.is_actionable

    def test_sale_wins_over_eggs(self):
        assert parse("sold 480 eggs", today=TODAY).intent is Intent.RECORD_SALE

    def test_purchase_wins_over_feed(self):
        assert parse("bought 12 bags of feed", today=TODAY).intent is Intent.RECORD_FEED_PURCHASE


class TestParseMortality:
    def test_extracts_count_and_date(self):
        r = parse("three birds died this morning", today=TODAY)
        assert r.intent is Intent.RECORD_MORTALITY
        assert r.slots["count"] == 3
        assert r.slots["date"] == TODAY

    def test_extracts_flock_when_named(self):
        r = parse("we lost 2 birds in flock 3 yesterday", today=TODAY)
        assert r.slots["count"] == 2
        assert r.slots["flock_ref"] == "3"
        assert r.slots["date"] == date(2026, 7, 21)

    def test_omits_flock_when_not_named(self):
        r = parse("three birds died", today=TODAY)
        assert "flock_ref" not in r.slots

    def test_extracts_stated_cause(self):
        r = parse("lost 4 birds from heat yesterday", today=TODAY)
        assert r.slots["count"] == 4
        assert "heat" in r.slots["cause"]


class TestParseEggs:
    def test_plain_count(self):
        r = parse("collected 945 eggs today", today=TODAY)
        assert r.slots["count"] == 945

    def test_trays_convert_to_eggs(self):
        """
        Kenyan farmers count in trays. Recording 12 instead of 360 would
        understate production by thirty times.
        """
        r = parse("collected 12 trays today", today=TODAY)
        assert r.slots["count"] == 12 * EGGS_PER_TRAY
        assert any("tray" in a for a in r.assumptions)

    def test_broken_eggs(self):
        r = parse("collected 300 eggs, 5 were broken", today=TODAY)
        assert r.slots["count"] == 300
        assert r.slots["broken"] == 5


class TestParseFeed:
    def test_bags_convert_to_kg_and_flag_assumption(self):
        r = parse("i bought 12 bags of growers mash", today=TODAY)
        assert r.slots["bags"] == 12
        assert r.slots["quantity_kg"] == Decimal(600)
        assert r.slots["feed_type"] == "Growers Mash"
        assert any("50kg" in a or "50" in a for a in r.assumptions)

    def test_unit_price_when_each(self):
        r = parse("bought 12 bags of layers mash at 3,250 each", today=TODAY)
        assert r.slots["unit_price"] == Decimal(3250)

    def test_kg_directly(self):
        r = parse("bought 150 kg of feed", today=TODAY)
        assert r.slots["quantity_kg"] == Decimal(150)


class TestParseVaccination:
    def test_vaccine_and_date(self):
        r = parse("we vaccinated newcastle today", today=TODAY)
        assert r.slots["vaccine_name"] == "Newcastle Disease (ND)"
        assert r.slots["date"] == TODAY

    def test_flock_and_dose(self):
        r = parse("gave flock 3 the gumboro dose 2 yesterday", today=TODAY)
        assert r.slots["flock_ref"] == "3"
        assert r.slots["dose_number"] == 2


class TestParseWeight:
    def test_average_weight_in_kg(self):
        r = parse("we weighed flock 2, average 1.8 kg", today=TODAY)
        assert r.slots["average_weight_kg"] == Decimal("1.8")
        assert r.slots["flock_ref"] == "2"

    def test_grams_convert_to_kg(self):
        r = parse("weighed the birds, average 850 g", today=TODAY)
        assert r.slots["average_weight_kg"] == Decimal("0.85")

    def test_weight_without_number_leaves_slot_empty(self):
        """"We weighed the birds today" is an opening, not a record."""
        r = parse("we weighed the birds today", today=TODAY)
        assert r.intent is Intent.RECORD_WEIGHT
        assert "average_weight_kg" not in r.slots


class TestNoInvention:
    """
    The guarantee, stated as tests. Nothing in a parse may appear that was not
    in the sentence.
    """

    @pytest.mark.parametrize(
        "text",
        [
            "three birds died",
            "collected some eggs",
            "we vaccinated the birds",
            "we weighed the birds today",
        ],
    )
    def test_never_invents_a_flock(self, text):
        assert "flock_ref" not in parse(text, today=TODAY).slots

    def test_never_invents_a_count(self):
        r = parse("we lost some birds today", today=TODAY)
        assert "count" not in r.slots

    def test_never_invents_money(self):
        r = parse("i bought 12 bags of feed", today=TODAY)
        assert "amount" not in r.slots
        assert "unit_price" not in r.slots

    def test_empty_input_is_unknown(self):
        r = parse("", today=TODAY)
        assert r.intent is Intent.UNKNOWN
        assert r.slots == {}
