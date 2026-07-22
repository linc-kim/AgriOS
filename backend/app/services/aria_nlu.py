"""
ARIA — deterministic natural-language understanding.

This module turns "we lost three birds in flock 2 this morning" into a typed
intent with typed slots. It is deliberately boring technology: regular
expressions, vocabulary tables and scoring rules. No model, no network, no
database.

Three reasons it has to be this way.

*It must work offline.* Module 13 requires that recording data, vaccinations,
inventory, finance and scheduling all function without Gemini or Claude. A
farmer in Kiambu with no signal still needs to record a mortality.

*It must be honest.* AR-01 (frozen) says ARIA never touches the database. The
engine that decides what to write is therefore not allowed to be a language
model — it is this file, which a reviewer can read end to end and predict
exactly. The LLM's role stays where it belongs: explaining things.

*It must be testable.* Every function here is pure. Given a string it returns
the same parse forever, so the test suite can pin behaviour on hundreds of
phrasings without a database or an API key.

What it deliberately does not do: it never guesses a flock, never invents a
date it did not see, and never fills a required slot to make a sentence
parseable. Missing information comes back as missing, and `aria_dialogue`
asks about it. A parser that guesses would produce exactly the invented farm
data the whole product forbids.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any


# ── Intents ──────────────────────────────────────────────────────────────────


class Intent(str, Enum):
    """
    What the farmer is trying to do.

    Only write intents live here. Questions ("how is my feed stock?") are not
    an intent — they fall through to `UNKNOWN` and are handled by the existing
    Q&A path, which is what should answer them.
    """

    RECORD_MORTALITY = "record_mortality"
    RECORD_EGGS = "record_eggs"
    RECORD_FEED_PURCHASE = "record_feed_purchase"
    RECORD_FEED_CONSUMPTION = "record_feed_consumption"
    RECORD_VACCINATION = "record_vaccination"
    RECORD_WEIGHT = "record_weight"
    RECORD_SALE = "record_sale"
    RECORD_EXPENSE = "record_expense"
    UNKNOWN = "unknown"


# ── Units and domain vocabulary ──────────────────────────────────────────────

#: A tray is 30 eggs across Kenyan poultry trade. Farmers say "twelve trays"
#: far more often than "three hundred and sixty eggs", so the parser has to
#: know the conversion or it will record an egg count 30× too low.
EGGS_PER_TRAY = 30

#: Standard feed bag. Farmers say "bags"; the schema wants kilograms. This is
#: the conventional size, not a universal truth — `bag_weight_kg` stays on the
#: parse so the dialogue layer can confirm it when the number matters.
DEFAULT_BAG_KG = Decimal("50")

#: Swahili is a first-class product language, not a translation layer, so the
#: vocabulary tables carry both. Kept as flat term lists rather than a general
#: translation step: matching "walikufa" directly is more reliable than trying
#: to translate a whole sentence before parsing it.
_MORTALITY_TERMS = (
    "died", "die", "dead", "death", "deaths", "lost", "loss", "losses",
    "mortality", "culled", "cull", "perished",
    # Swahili
    "kufa", "walikufa", "amekufa", "wamekufa", "vifo", "alikufa",
)
_EGG_TERMS = ("egg", "eggs", "tray", "trays", "crate", "crates", "mayai", "treya")
_FEED_TERMS = (
    "feed", "mash", "pellets", "crumbs", "starter", "grower", "growers",
    "finisher", "layer", "layers mash", "chakula", "pumba",
)
_VACCINE_TERMS = ("vaccinat", "vaccine", "jab", "immunis", "immuniz", "chanjo")
_WEIGH_TERMS = ("weigh", "weighed", "weight", "uzito", "kupima")
_SALE_TERMS = ("sold", "sell", "sale", "kuuza", "niliuza")
_PURCHASE_TERMS = ("bought", "buy", "purchase", "purchased", "nilinunua", "kununua")
_CONSUMPTION_TERMS = ("fed", "feeding", "consumed", "used", "gave", "finished")
_COST_TERMS = ("cost", "costs", "paid", "price", "priced", "spent", "bei", "gharama")

#: Vaccines a Kenyan poultry farmer actually names, with the canonical form the
#: health module stores. Anything unrecognised is still accepted — it is passed
#: through verbatim and confirmed — because a vocabulary list must never be the
#: reason a real vaccination cannot be recorded.
VACCINE_ALIASES: dict[str, str] = {
    "newcastle": "Newcastle Disease (ND)",
    "nd": "Newcastle Disease (ND)",
    "gumboro": "Infectious Bursal Disease (Gumboro)",
    "ibd": "Infectious Bursal Disease (Gumboro)",
    "mareks": "Marek's Disease",
    "marek": "Marek's Disease",
    "fowl pox": "Fowl Pox",
    "fowlpox": "Fowl Pox",
    "fowl typhoid": "Fowl Typhoid",
    "typhoid": "Fowl Typhoid",
    "ib": "Infectious Bronchitis (IB)",
    "infectious bronchitis": "Infectious Bronchitis (IB)",
    "de-beaking": "De-beaking",
    "coccidiosis": "Coccidiosis Vaccine",
}

#: Written numbers. Farmers dictate "three birds died" far more than "3".
_WORD_NUMBERS: dict[str, int] = {
    "a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
    "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
    "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19,
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60,
    "seventy": 70, "eighty": 80, "ninety": 90, "hundred": 100,
    # Swahili
    "moja": 1, "mbili": 2, "tatu": 3, "nne": 4, "tano": 5, "sita": 6,
    "saba": 7, "nane": 8, "tisa": 9, "kumi": 10,
}

_WEEKDAYS = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}


# ── Parse result ─────────────────────────────────────────────────────────────


@dataclass
class ParsedUtterance:
    """
    The result of reading one sentence.

    `slots` holds only what was actually found. A key being absent is
    meaningful — it is what drives the follow-up questions — so nothing here
    is ever defaulted into place.
    """

    intent: Intent
    slots: dict[str, Any] = field(default_factory=dict)
    #: 0–1. Drives whether ARIA acts, asks, or hands off to the Q&A path.
    confidence: float = 0.0
    #: Human-readable notes about assumptions made, surfaced in confirmation.
    assumptions: list[str] = field(default_factory=list)
    raw_text: str = ""

    @property
    def is_actionable(self) -> bool:
        return self.intent is not Intent.UNKNOWN and self.confidence >= 0.5


# ── Normalisation ────────────────────────────────────────────────────────────


def normalise(text: str) -> str:
    """Lowercase, strip accents, collapse whitespace, drop terminal punctuation."""
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    return text


# ── Number, money, quantity ──────────────────────────────────────────────────

# Digits with optional thousands separators and decimals: 945, 3,250, 2.5
_NUM_RE = re.compile(r"(?<![\w.])(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)(?![\w])")

# "3.2k" / "15k" — common shorthand for money.
_K_RE = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)\s*k(?![\w])")


def _to_decimal(raw: str) -> Decimal | None:
    try:
        return Decimal(raw.replace(",", ""))
    except (InvalidOperation, ValueError):
        return None


def extract_numbers(text: str) -> list[Decimal]:
    """Every number in the sentence, digits or words, in order of appearance."""
    found: list[tuple[int, Decimal]] = []

    for m in _NUM_RE.finditer(text):
        value = _to_decimal(m.group(1))
        if value is not None:
            found.append((m.start(), value))

    # Word numbers, including two-token forms like "twenty five".
    tokens = list(re.finditer(r"[a-z]+", text))
    i = 0
    while i < len(tokens):
        word = tokens[i].group(0)
        if word in _WORD_NUMBERS:
            value = _WORD_NUMBERS[word]
            # "twenty five" → 25, but only for the tens that combine this way.
            if value in (20, 30, 40, 50, 60, 70, 80, 90) and i + 1 < len(tokens):
                nxt = tokens[i + 1].group(0)
                if nxt in _WORD_NUMBERS and _WORD_NUMBERS[nxt] < 10:
                    value += _WORD_NUMBERS[nxt]
                    i += 1
            found.append((tokens[i].start(), Decimal(value)))
        i += 1

    return [v for _, v in sorted(found, key=lambda p: p[0])]


def extract_money(text: str) -> Decimal | None:
    """
    A monetary amount, if the sentence clearly names one.

    Requires an explicit signal — a currency token, a cost word, or the "k"
    shorthand. Without one this returns None even when a number is present,
    because "12 bags" must never be read as twelve shillings.
    """
    m = _K_RE.search(text)
    if m:
        value = _to_decimal(m.group(1))
        if value is not None:
            return value * 1000

    currency = re.search(
        r"(?:kes|ksh|kshs|shillings?|bob|/=)\s*([\d,]+(?:\.\d+)?)"
        r"|([\d,]+(?:\.\d+)?)\s*(?:kes|ksh|kshs|shillings?|bob|/=)",
        text,
    )
    if currency:
        return _to_decimal(currency.group(1) or currency.group(2))

    # "at 3,250 each" / "at 3250 per bag" — a price with no cost word in sight.
    # Common enough in real phrasing that omitting it lost the unit price on
    # most feed purchases.
    m = re.search(r"\bat\s+([\d,]+(?:\.\d+)?)\s*(?:each|per\b|a\b|/)", text)
    if m:
        return _to_decimal(m.group(1))

    if any(t in text for t in _COST_TERMS):
        # "feed cost 3,250 each" — take the number nearest the cost word.
        nums = extract_numbers(text)
        if nums:
            return max(nums)

    return None


@dataclass
class Quantity:
    amount: Decimal
    unit: str


_UNIT_PATTERNS: list[tuple[str, str]] = [
    (r"\b(bags?|gunia|magunia)\b", "bag"),
    (r"\b(kgs?|kilos?|kilogram(?:me)?s?)\b", "kg"),
    (r"\b(litres?|liters?|l)\b", "litre"),
    (r"\b(trays?|treya|crates?)\b", "tray"),
    (r"\b(eggs?|mayai)\b", "egg"),
    (r"\b(birds?|chickens?|hens?|layers?|broilers?|kuku)\b", "bird"),
    (r"\b(grams?|g)\b", "gram"),
]


def extract_quantity(text: str) -> Quantity | None:
    """
    The first "<number> <unit>" pair in the sentence.

    Scans for a unit and then looks backwards for the nearest preceding number,
    which is how the phrasing actually runs — "12 bags", "three birds",
    "945 eggs". A unit with no number before it yields nothing rather than a
    guess of 1.
    """
    for pattern, unit in _UNIT_PATTERNS:
        m = re.search(pattern, text)
        if not m:
            continue
        before = text[: m.start()]

        digits = list(_NUM_RE.finditer(before))
        words = [t for t in re.finditer(r"[a-z]+", before) if t.group(0) in _WORD_NUMBERS]

        best_pos, best_val = -1, None
        if digits:
            last = digits[-1]
            if last.start() > best_pos:
                best_pos, best_val = last.start(), _to_decimal(last.group(1))
        if words:
            last = words[-1]
            if last.start() > best_pos:
                best_pos, best_val = last.start(), Decimal(_WORD_NUMBERS[last.group(0)])

        # Only accept if the number is close by — "we lost 3 birds, feed is
        # low, buy bags" must not bind 3 to "bags".
        if best_val is not None and len(before) - best_pos <= 24:
            return Quantity(amount=best_val, unit=unit)

    return None


# ── Dates ────────────────────────────────────────────────────────────────────


def extract_date(text: str, *, today: date | None = None) -> tuple[date | None, str | None]:
    """
    Resolve a relative or explicit date.

    Returns (date, assumption). The assumption is a sentence for the
    confirmation step whenever the date was inferred rather than stated —
    a farmer recording yesterday's mortality against today's date is a real
    data error, so an inferred date is always shown back.
    """
    today = today or date.today()

    if re.search(r"\b(today|this morning|this evening|this afternoon|leo|now|just now)\b", text):
        return today, None
    if re.search(r"\b(yesterday|last night|jana)\b", text):
        return today - timedelta(days=1), None
    if re.search(r"\bday before yesterday\b", text):
        return today - timedelta(days=2), None

    m = re.search(r"\b(\d+)\s+days?\s+ago\b", text)
    if m:
        return today - timedelta(days=int(m.group(1))), None

    m = re.search(r"\blast\s+(" + "|".join(_WEEKDAYS) + r")\b", text)
    if m:
        target = _WEEKDAYS[m.group(1)]
        delta = (today.weekday() - target) % 7 or 7
        return today - timedelta(days=delta), None

    m = re.search(r"\bon\s+(" + "|".join(_WEEKDAYS) + r")\b", text)
    if m:
        target = _WEEKDAYS[m.group(1)]
        delta = (today.weekday() - target) % 7
        return today - timedelta(days=delta or 7), None

    # Explicit: 2026-07-21, 21/07/2026, 21/07
    m = re.search(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", text)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3))), None
        except ValueError:
            pass
    m = re.search(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b", text)
    if m:
        try:
            year = int(m.group(3) or today.year)
            if year < 100:
                year += 2000
            return date(year, int(m.group(2)), int(m.group(1))), None
        except ValueError:
            pass

    # Nothing stated. Today is the overwhelmingly common case for farm
    # recording, but it is an assumption and gets surfaced as one.
    return today, "I recorded this as today — tell me if it was another day."


# ── Flock reference ──────────────────────────────────────────────────────────


def extract_flock_reference(text: str) -> str | None:
    """
    A flock the farmer named, as free text for the resolver to match.

    Returns the *reference*, never a flock id — resolving it needs the database,
    which this module does not touch. An unmatched or ambiguous reference
    becomes a follow-up question rather than a guess.
    """
    m = re.search(r"\bflock\s+([a-z0-9][\w-]*)\b", text)
    if m:
        return m.group(1)
    m = re.search(r"\b(?:house|pen|unit|batch)\s+([a-z0-9][\w-]*)\b", text)
    if m:
        return m.group(1)
    # "in alpha" / "from alpha" — only for clearly name-like tokens.
    m = re.search(r"\b(?:in|from|for)\s+(alpha|beta|gamma|delta|omega)\b", text)
    if m:
        return m.group(1)
    return None


def extract_vaccine(text: str) -> str | None:
    """Canonical vaccine name, or the farmer's own words if unrecognised."""
    for alias, canonical in VACCINE_ALIASES.items():
        if re.search(rf"\b{re.escape(alias)}\b", text):
            return canonical

    m = re.search(
        r"\b(?:vaccinated|vaccinate|vaccine|gave|administered)\s+(?:against\s+|for\s+|with\s+)?"
        r"([a-z][a-z\s'-]{2,30}?)\s*(?:vaccine|today|yesterday|to|in|on|$)",
        text,
    )
    if m:
        candidate = m.group(1).strip()
        noise = {"the", "them", "birds", "chickens", "flock", "all", "my", "our", "a", "an"}
        if candidate and candidate not in noise and len(candidate) > 2:
            return candidate.title()
    return None


# ── Intent classification ────────────────────────────────────────────────────


def _has(text: str, terms: tuple[str, ...]) -> bool:
    return any(t in text for t in terms)


def classify_intent(text: str) -> tuple[Intent, float]:
    """
    Pick the intent and say how sure we are.

    Order matters: the checks run most-specific first, because several of these
    share vocabulary. "Sold 480 eggs" contains an egg term but is a sale, and
    "bought 12 bags of feed" contains a feed term but is a purchase. Scoring
    alone would make those coin flips, so precedence does the work instead.
    """
    # A question is not a record. Checked first so "how many birds died?" is
    # never treated as a mortality entry.
    if re.match(r"^\s*(what|why|how|when|which|who|where|is|are|do|does|can|should)\b", text) \
            or text.rstrip().endswith("?"):
        return Intent.UNKNOWN, 0.0

    if _has(text, _VACCINE_TERMS):
        return Intent.RECORD_VACCINATION, 0.95

    # Naming a vaccine *is* the signal. Farmers say "gave them Gumboro
    # yesterday" without ever using the word "vaccinate", and requiring the
    # verb meant those sentences fell through to the Q&A path unrecorded.
    if any(re.search(rf"\b{re.escape(alias)}\b", text) for alias in VACCINE_ALIASES):
        return Intent.RECORD_VACCINATION, 0.88

    if _has(text, _WEIGH_TERMS) and not _has(text, _COST_TERMS):
        return Intent.RECORD_WEIGHT, 0.9

    if _has(text, _SALE_TERMS):
        return Intent.RECORD_SALE, 0.92

    if _has(text, _MORTALITY_TERMS):
        # "lost" is ambiguous — "lost 3 birds" vs "lost the receipt".
        if _has(text, ("bird", "chicken", "hen", "layer", "broiler", "kuku", "chick")) \
                or re.search(r"\b(died|dead|death|mortality|walikufa|vifo|culled)\b", text):
            return Intent.RECORD_MORTALITY, 0.94
        return Intent.RECORD_MORTALITY, 0.6

    if _has(text, _PURCHASE_TERMS):
        if _has(text, _FEED_TERMS):
            return Intent.RECORD_FEED_PURCHASE, 0.93
        return Intent.RECORD_EXPENSE, 0.75

    if _has(text, _EGG_TERMS):
        if re.search(r"\b(collect|collected|picked|gathered|got|kukusanya)\b", text):
            return Intent.RECORD_EGGS, 0.94
        return Intent.RECORD_EGGS, 0.7

    if _has(text, _FEED_TERMS) and _has(text, _CONSUMPTION_TERMS):
        return Intent.RECORD_FEED_CONSUMPTION, 0.85

    if _has(text, _COST_TERMS):
        return Intent.RECORD_EXPENSE, 0.7

    return Intent.UNKNOWN, 0.0


# ── Top-level parse ──────────────────────────────────────────────────────────


def parse(text: str, *, today: date | None = None) -> ParsedUtterance:
    """
    Read one utterance into an intent and whatever slots it actually contained.

    Slots that were not stated are simply absent. That is the contract the
    dialogue layer depends on, and the reason ARIA can promise it never invents
    farm data: there is no code path here that fabricates a value.
    """
    raw = text or ""
    norm = normalise(raw)
    intent, confidence = classify_intent(norm)

    result = ParsedUtterance(
        intent=intent, confidence=confidence, raw_text=raw,
    )
    if intent is Intent.UNKNOWN:
        return result

    slots: dict[str, Any] = {}
    assumptions: list[str] = []

    when, assumption = extract_date(norm, today=today)
    if when:
        slots["date"] = when
    if assumption:
        assumptions.append(assumption)

    flock_ref = extract_flock_reference(norm)
    if flock_ref:
        slots["flock_ref"] = flock_ref

    qty = extract_quantity(norm)
    money = extract_money(norm)
    numbers = extract_numbers(norm)

    if intent is Intent.RECORD_MORTALITY:
        if qty and qty.unit in ("bird", "egg"):
            slots["count"] = int(qty.amount)
        elif numbers:
            slots["count"] = int(numbers[0])
        cause = _extract_cause(norm)
        if cause:
            slots["cause"] = cause

    elif intent in (Intent.RECORD_EGGS, Intent.RECORD_SALE):
        if qty and qty.unit == "tray":
            slots["count"] = int(qty.amount) * EGGS_PER_TRAY
            assumptions.append(
                f"{int(qty.amount)} trays = {int(qty.amount) * EGGS_PER_TRAY} eggs "
                f"at {EGGS_PER_TRAY} per tray."
            )
        elif qty and qty.unit == "egg":
            slots["count"] = int(qty.amount)
        elif numbers:
            slots["count"] = int(numbers[0])
        if money:
            slots["amount"] = money
        broken = re.search(r"\b(\d+)\s+(?:were\s+)?(?:broken|cracked|damaged)\b", norm)
        if broken:
            slots["broken"] = int(broken.group(1))

    elif intent in (Intent.RECORD_FEED_PURCHASE, Intent.RECORD_FEED_CONSUMPTION):
        if qty and qty.unit == "bag":
            slots["bags"] = int(qty.amount)
            slots["quantity_kg"] = qty.amount * DEFAULT_BAG_KG
            slots["bag_weight_kg"] = DEFAULT_BAG_KG
            assumptions.append(
                f"I assumed {DEFAULT_BAG_KG:g}kg bags — say so if yours differ."
            )
        elif qty and qty.unit == "kg":
            slots["quantity_kg"] = qty.amount
        feed_type = _extract_feed_type(norm)
        if feed_type:
            slots["feed_type"] = feed_type
        if money:
            slots["unit_price" if re.search(r"\beach\b|\bper\b", norm) else "amount"] = money

    elif intent is Intent.RECORD_VACCINATION:
        vaccine = extract_vaccine(norm)
        if vaccine:
            slots["vaccine_name"] = vaccine
        dose = re.search(r"\b(?:dose|round)\s*(\d+)\b|\b(\d+)(?:st|nd|rd|th)\s+dose\b", norm)
        if dose:
            slots["dose_number"] = int(dose.group(1) or dose.group(2))

    elif intent is Intent.RECORD_WEIGHT:
        weight = re.search(r"\b(\d+(?:\.\d+)?)\s*(kgs?|kilos?|g|grams?)\b", norm)
        if weight:
            value = _to_decimal(weight.group(1))
            if value is not None:
                if weight.group(2).startswith("g") and not weight.group(2).startswith("kg"):
                    value = value / 1000
                slots["average_weight_kg"] = value
        sample = re.search(r"\b(?:sample|weighed|took)\s+(?:of\s+)?(\d+)\b", norm)
        if sample:
            slots["sample_size"] = int(sample.group(1))
        elif qty and qty.unit == "bird":
            slots["sample_size"] = int(qty.amount)

    elif intent is Intent.RECORD_EXPENSE:
        if money:
            slots["amount"] = money
        slots["description"] = raw.strip()[:300]

    result.slots = slots
    result.assumptions = assumptions
    return result


def _extract_cause(text: str) -> str | None:
    """A stated cause of death, when the farmer volunteered one."""
    m = re.search(
        r"\b(?:from|due to|because of|of)\s+([a-z][a-z\s'-]{2,40}?)"
        r"\s*(?:today|yesterday|in|on|$)",
        text,
    )
    if m:
        candidate = m.group(1).strip()
        if candidate and candidate not in {"the", "them", "it", "this", "that"}:
            return candidate[:100]
    for keyword in ("heat", "cold", "predator", "disease", "suffocation", "crushing", "stress"):
        if keyword in text:
            return keyword
    return None


def _extract_feed_type(text: str) -> str | None:
    """Which feed, in the farmer's words, normalised lightly."""
    for pattern, label in (
        (r"\b(?:layers?|layer)\s*(?:mash|pellets?)?\b", "Layers Mash"),
        (r"\b(?:growers?|grower)\s*(?:mash|pellets?)?\b", "Growers Mash"),
        (r"\b(?:starter|chick)\s*(?:mash|crumbs?)?\b", "Chick Starter"),
        (r"\b(?:finisher)\s*(?:mash|pellets?)?\b", "Finisher"),
        (r"\bbroiler\s*(?:starter|finisher|mash)?\b", "Broiler Feed"),
    ):
        if re.search(pattern, text):
            return label
    return None
