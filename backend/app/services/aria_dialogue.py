"""
ARIA — reverse interviewing.

The parser says what a sentence contained. This module decides what is still
missing, asks for it, and refuses to write anything until the record would be
correct. It is the difference between an assistant and a data-entry hazard:
"three birds died" is not a recordable fact until we know *which flock*.

Design notes worth keeping.

*Two tiers of question, not one.* `required` slots block the write — without
them the record is wrong or impossible. `probes` are clinical context (symptoms,
sudden onset, isolation) that make the disease-risk engine useful later. Probes
never block. This distinction is the whole UX argument: a farmer recording three
dead birds on a phone in a wet coop will abandon a seven-question interrogation,
and an assistant nobody uses records nothing at all. So we ask what we must,
save, and *then* offer to learn more.

*Probes are asked when they are worth asking.* Mortality gets them, because a
cluster of deaths is the signal the whole health module exists to catch. A
routine egg count does not. `should_probe` holds that policy in one place.

*Confirmation is always explicit.* Nothing reaches the database until the farmer
sees a plain-language summary and agrees. Combined with the parser never
inventing slots, that is what makes the AR-01 override safe: a language model is
nowhere in this path, and the human sees the payload before it lands.

This module is pure. It takes state and an utterance and returns new state and a
reply. Resolving a flock reference to an id needs the database, so it does not
happen here — the caller resolves and hands back candidates.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Any

from app.services.aria_nlu import Intent, ParsedUtterance, parse


class Stage(str, Enum):
    """Where a recording conversation has got to."""

    COLLECTING = "collecting"      # still missing a required slot
    PROBING = "probing"            # required slots done, gathering context
    CONFIRMING = "confirming"      # summary shown, waiting for yes/no
    READY = "ready"                # confirmed — the caller may now write
    CANCELLED = "cancelled"
    ABANDONED = "abandoned"        # farmer changed subject


@dataclass
class SlotSpec:
    name: str
    question: str
    #: How to read a bare answer ("flock 2", "three", "yes") for this slot.
    kind: str = "text"


@dataclass
class IntentSpec:
    intent: Intent
    label: str
    required: list[SlotSpec] = field(default_factory=list)
    probes: list[SlotSpec] = field(default_factory=list)


# ── What each intent needs before it can be written ──────────────────────────
#
# Kept deliberately small. Every extra required slot is another question
# between a farmer and a recorded fact, so a slot earns its place here only if
# the record is genuinely wrong without it.

FLOCK = SlotSpec("flock_ref", "Which flock was this?", kind="flock")
DATE = SlotSpec("date", "Which day was this?", kind="date")

INTENT_SPECS: dict[Intent, IntentSpec] = {
    Intent.RECORD_MORTALITY: IntentSpec(
        intent=Intent.RECORD_MORTALITY,
        label="mortality",
        required=[FLOCK, SlotSpec("count", "How many birds did you lose?", kind="int")],
        # The clinical picture. These feed disease risk, which is the reason
        # mortality gets probed at all and an egg count does not.
        probes=[
            SlotSpec("symptoms", "Did you notice any symptoms — coughing, diarrhoea, swelling?"),
            SlotSpec("sudden", "Did they die suddenly, or had they been unwell?"),
            SlotSpec("others_affected", "Are any other birds showing the same signs?"),
        ],
    ),
    Intent.RECORD_EGGS: IntentSpec(
        intent=Intent.RECORD_EGGS,
        label="egg production",
        required=[FLOCK, SlotSpec("count", "How many eggs did you collect?", kind="int")],
    ),
    Intent.RECORD_FEED_PURCHASE: IntentSpec(
        intent=Intent.RECORD_FEED_PURCHASE,
        label="feed purchase",
        required=[
            SlotSpec("quantity_kg", "How much feed did you buy?", kind="quantity"),
            SlotSpec("amount", "What did it cost in total?", kind="money"),
        ],
        probes=[SlotSpec("feed_type", "Which feed was it — layers, growers, starter?")],
    ),
    Intent.RECORD_FEED_CONSUMPTION: IntentSpec(
        intent=Intent.RECORD_FEED_CONSUMPTION,
        label="feed use",
        required=[FLOCK, SlotSpec("quantity_kg", "How much feed did they use?", kind="quantity")],
    ),
    Intent.RECORD_VACCINATION: IntentSpec(
        intent=Intent.RECORD_VACCINATION,
        label="vaccination",
        required=[FLOCK, SlotSpec("vaccine_name", "Which vaccine did you give?")],
        probes=[SlotSpec("route", "How was it given — drinking water, eye drop, injection?")],
    ),
    Intent.RECORD_WEIGHT: IntentSpec(
        intent=Intent.RECORD_WEIGHT,
        label="weigh-in",
        required=[
            FLOCK,
            SlotSpec("sample_size", "How many birds did you weigh?", kind="int"),
            SlotSpec("average_weight_kg", "What was the average weight?", kind="weight"),
        ],
    ),
    Intent.RECORD_SALE: IntentSpec(
        intent=Intent.RECORD_SALE,
        label="sale",
        required=[
            SlotSpec("count", "How many did you sell?", kind="int"),
            SlotSpec("amount", "What did you receive in total?", kind="money"),
        ],
    ),
    Intent.RECORD_EXPENSE: IntentSpec(
        intent=Intent.RECORD_EXPENSE,
        label="expense",
        required=[SlotSpec("amount", "How much did you spend?", kind="money")],
    ),
}


@dataclass
class DialogueState:
    """
    One in-flight recording conversation.

    Serialisable to JSON so it can live on the conversation row between turns —
    a farmer who asks "what's my feed stock?" mid-way through recording a
    mortality must be able to come back to it.
    """

    intent: Intent
    stage: Stage = Stage.COLLECTING
    slots: dict[str, Any] = field(default_factory=dict)
    assumptions: list[str] = field(default_factory=list)
    #: Slot currently being asked about, so a bare answer knows where to land.
    pending: str | None = None
    #: Probes already asked, so we never ask the same thing twice.
    asked_probes: list[str] = field(default_factory=list)
    #: Candidate flocks when a reference matched more than one.
    flock_choices: list[dict[str, str]] = field(default_factory=list)

    @property
    def spec(self) -> IntentSpec:
        return INTENT_SPECS[self.intent]

    def missing_required(self) -> list[SlotSpec]:
        return [s for s in self.spec.required if self.slots.get(s.name) in (None, "")]

    def next_probe(self) -> SlotSpec | None:
        for probe in self.spec.probes:
            if probe.name not in self.asked_probes and probe.name not in self.slots:
                return probe
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent": self.intent.value,
            "stage": self.stage.value,
            "slots": _jsonable(self.slots),
            "assumptions": self.assumptions,
            "pending": self.pending,
            "asked_probes": self.asked_probes,
            "flock_choices": self.flock_choices,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "DialogueState":
        return cls(
            intent=Intent(raw["intent"]),
            stage=Stage(raw.get("stage", Stage.COLLECTING.value)),
            slots=_from_jsonable(raw.get("slots", {})),
            assumptions=list(raw.get("assumptions", [])),
            pending=raw.get("pending"),
            asked_probes=list(raw.get("asked_probes", [])),
            flock_choices=list(raw.get("flock_choices", [])),
        )


@dataclass
class Reply:
    """What ARIA says back, and what the caller should do about it."""

    text: str
    stage: Stage
    #: Tappable answers for the UI. Never the only way to answer.
    options: list[str] = field(default_factory=list)
    #: Present when stage is READY — the payload the caller may write.
    payload: dict[str, Any] | None = None


# ── Serialisation helpers ────────────────────────────────────────────────────


def _jsonable(slots: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in slots.items():
        if isinstance(v, date):
            out[k] = v.isoformat()
        elif isinstance(v, Decimal):
            out[k] = str(v)
        else:
            out[k] = v
    return out


#: Slots whose JSON form must be restored to a real type. Kept explicit rather
#: than inferred — guessing that any digit-ish string is a Decimal would mangle
#: free text like a vaccine batch number.
_DATE_SLOTS = {"date"}
_DECIMAL_SLOTS = {"quantity_kg", "amount", "unit_price", "average_weight_kg", "bag_weight_kg"}


def _from_jsonable(raw: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in raw.items():
        if k in _DATE_SLOTS and isinstance(v, str):
            try:
                out[k] = date.fromisoformat(v)
                continue
            except ValueError:
                pass
        if k in _DECIMAL_SLOTS and isinstance(v, (str, int, float)):
            try:
                out[k] = Decimal(str(v))
                continue
            except Exception:
                pass
        out[k] = v
    return out


# ── Answer interpretation ────────────────────────────────────────────────────

_YES = {"yes", "yeah", "yep", "y", "correct", "right", "ok", "okay", "sure",
        "save", "confirm", "ndio", "sawa", "ndiyo"}
_NO = {"no", "nope", "n", "wrong", "cancel", "stop", "hapana", "la"}
_SKIP = {"skip", "dont know", "don't know", "not sure", "no idea", "sijui", "next", "none"}


def interpret_yes_no(text: str) -> bool | None:
    t = (text or "").strip().lower().rstrip(".!")
    if t in _YES:
        return True
    if t in _NO:
        return False
    # Leading word covers "yes save it", "no that's wrong".
    first = t.split()[0] if t.split() else ""
    if first in _YES:
        return True
    if first in _NO:
        return False
    return None


def is_skip(text: str) -> bool:
    t = (text or "").strip().lower().rstrip(".!")
    return t in _SKIP or any(t.startswith(s) for s in _SKIP)


def _coerce(kind: str, text: str, *, today: date | None = None) -> Any:
    """
    Read a bare answer for a slot of the given kind.

    Reuses the parser rather than re-implementing extraction, so "about three"
    and "3" and "three birds" all land the same way whether they arrive in the
    opening sentence or as an answer to a follow-up.
    """
    from app.services import aria_nlu

    norm = aria_nlu.normalise(text)

    if kind == "int":
        nums = aria_nlu.extract_numbers(norm)
        return int(nums[0]) if nums else None
    if kind == "money":
        money = aria_nlu.extract_money(norm)
        if money is not None:
            return money
        nums = aria_nlu.extract_numbers(norm)
        return nums[0] if nums else None
    if kind == "quantity":
        qty = aria_nlu.extract_quantity(norm)
        if qty:
            if qty.unit == "bag":
                return qty.amount * aria_nlu.DEFAULT_BAG_KG
            if qty.unit == "kg":
                return qty.amount
        nums = aria_nlu.extract_numbers(norm)
        return nums[0] if nums else None
    if kind == "weight":
        nums = aria_nlu.extract_numbers(norm)
        if not nums:
            return None
        value = nums[0]
        # Bare numbers above 20 in a weight answer are almost certainly grams.
        if "g" in norm and "kg" not in norm:
            value = value / 1000
        return value
    if kind == "date":
        when, _ = aria_nlu.extract_date(norm, today=today)
        return when
    if kind == "flock":
        ref = aria_nlu.extract_flock_reference(norm)
        if ref:
            return ref
        # A bare answer to "which flock?" is the flock name itself.
        stripped = norm.strip()
        return stripped or None

    return text.strip() or None


# ── The engine ───────────────────────────────────────────────────────────────


def begin(parsed: ParsedUtterance) -> DialogueState:
    """Open a recording conversation from an opening utterance."""
    return DialogueState(
        intent=parsed.intent,
        slots=dict(parsed.slots),
        assumptions=list(parsed.assumptions),
    )


def advance(
    state: DialogueState,
    utterance: str | None,
    *,
    today: date | None = None,
) -> tuple[DialogueState, Reply]:
    """
    Take one turn.

    Pass `utterance=None` to get the opening question without consuming input,
    which is what happens right after `begin`.
    """
    if utterance is not None:
        state = _absorb(state, utterance, today=today)
        if state.stage in (Stage.CANCELLED, Stage.ABANDONED):
            return state, Reply(
                text="No problem — I haven't saved anything.", stage=state.stage
            )
        if state.stage is Stage.READY:
            return state, Reply(
                text=_saved_summary(state),
                stage=Stage.READY,
                payload=build_payload(state),
            )

    return _next_question(state)


def _absorb(state: DialogueState, utterance: str, *, today: date | None) -> DialogueState:
    """Fold one answer into the state."""
    text = (utterance or "").strip()

    # An explicit stop always wins, at any stage.
    if interpret_yes_no(text) is False and state.stage is not Stage.CONFIRMING:
        if text.lower().strip().rstrip(".!") in {"cancel", "stop", "no"}:
            state.stage = Stage.CANCELLED
            return state

    if state.stage is Stage.CONFIRMING:
        answer = interpret_yes_no(text)
        if answer is True:
            state.stage = Stage.READY
            return state
        if answer is False:
            state.stage = Stage.CANCELLED
            return state
        # Not a yes/no — treat it as a correction and re-parse.
        state.stage = Stage.COLLECTING

    # A fresh, clearly-different intent means the farmer moved on. Recording
    # against a half-finished record they abandoned would be worse than losing
    # the draft.
    #
    # A pending question does not suppress this. "Collected 900 eggs in flock 1"
    # arriving while we wait for a flock is a new topic, not an answer — the
    # earlier version treated any input as an answer whenever something was
    # pending, which quietly filed an egg count as a mortality's flock. The
    # guard is the confidence bar instead: bare answers like "flock 2", "20" or
    # "1.8 kg" carry no intent verb and parse as UNKNOWN, so they never trip it.
    reparsed = parse(text, today=today)
    if (
        reparsed.intent is not state.intent
        and reparsed.intent is not Intent.UNKNOWN
        and reparsed.confidence >= 0.85
    ):
        state.stage = Stage.ABANDONED
        return state

    # Same intent restated with more detail — merge anything new.
    if reparsed.intent is state.intent:
        for key, value in reparsed.slots.items():
            if value not in (None, "") and key not in state.slots:
                state.slots[key] = value
        for note in reparsed.assumptions:
            if note not in state.assumptions:
                state.assumptions.append(note)

    # A bare answer lands in whatever slot we asked about.
    if state.pending:
        spec = _spec_for(state, state.pending)
        if is_skip(text):
            state.asked_probes.append(state.pending)
        else:
            value = _coerce(spec.kind if spec else "text", text, today=today)
            if value is not None:
                state.slots[state.pending] = value
            if spec and spec.name in [p.name for p in state.spec.probes]:
                state.asked_probes.append(spec.name)
        state.pending = None

    return state


def _spec_for(state: DialogueState, name: str) -> SlotSpec | None:
    for spec in list(state.spec.required) + list(state.spec.probes):
        if spec.name == name:
            return spec
    return None


def _next_question(state: DialogueState) -> tuple[DialogueState, Reply]:
    """Decide what to say next."""
    missing = state.missing_required()
    if missing:
        slot = missing[0]
        state.stage = Stage.COLLECTING
        state.pending = slot.name
        options: list[str] = []
        if slot.kind == "flock" and state.flock_choices:
            options = [c["label"] for c in state.flock_choices]
        return state, Reply(text=slot.question, stage=Stage.COLLECTING, options=options)

    if should_probe(state):
        probe = state.next_probe()
        if probe:
            state.stage = Stage.PROBING
            state.pending = probe.name
            return state, Reply(
                text=probe.question,
                stage=Stage.PROBING,
                options=["Skip"],
            )

    state.stage = Stage.CONFIRMING
    state.pending = None
    return state, Reply(
        text=_confirmation(state),
        stage=Stage.CONFIRMING,
        options=["Yes, save it", "No, cancel"],
    )


def should_probe(state: DialogueState) -> bool:
    """
    Whether this record is worth asking context questions about.

    Only mortality, and only up to three questions. The rule exists because
    probing everything would turn a five-second egg count into an interview,
    and a farmer who stops using ARIA records nothing at all. Mortality earns
    it: a cluster of deaths with symptoms is precisely what the disease-risk
    engine needs and what a farmer most needs help noticing.
    """
    if state.intent is not Intent.RECORD_MORTALITY:
        return False
    return len(state.asked_probes) < 3


# ── Summaries ────────────────────────────────────────────────────────────────


def _fmt_date(value: Any) -> str:
    if isinstance(value, date):
        return value.strftime("%-d %b") if hasattr(value, "strftime") else str(value)
    return str(value)


def describe(state: DialogueState) -> str:
    """One plain-language line describing the record about to be written."""
    s = state.slots
    when = s.get("date")
    when_txt = ""
    if isinstance(when, date):
        when_txt = f" on {when.isoformat()}"
    flock = s.get("flock_label") or s.get("flock_ref")
    flock_txt = f" in flock {flock}" if flock else ""

    if state.intent is Intent.RECORD_MORTALITY:
        return f"{s.get('count')} bird(s) lost{flock_txt}{when_txt}"
    if state.intent is Intent.RECORD_EGGS:
        broken = s.get("broken")
        extra = f", {broken} broken" if broken else ""
        return f"{s.get('count')} eggs collected{flock_txt}{when_txt}{extra}"
    if state.intent is Intent.RECORD_FEED_PURCHASE:
        kg = s.get("quantity_kg")
        feed = s.get("feed_type") or "feed"
        return f"{kg}kg of {feed} bought for KES {s.get('amount')}{when_txt}"
    if state.intent is Intent.RECORD_FEED_CONSUMPTION:
        return f"{s.get('quantity_kg')}kg of feed used{flock_txt}{when_txt}"
    if state.intent is Intent.RECORD_VACCINATION:
        return f"{s.get('vaccine_name')} given{flock_txt}{when_txt}"
    if state.intent is Intent.RECORD_WEIGHT:
        return (
            f"{s.get('sample_size')} birds weighed{flock_txt}, "
            f"average {s.get('average_weight_kg')}kg{when_txt}"
        )
    if state.intent is Intent.RECORD_SALE:
        return f"{s.get('count')} sold for KES {s.get('amount')}{when_txt}"
    return f"expense of KES {s.get('amount')}{when_txt}"


def _confirmation(state: DialogueState) -> str:
    lines = [f"Ready to record: {describe(state)}."]
    if state.assumptions:
        lines.append(" ".join(state.assumptions))
    lines.append("Shall I save it?")
    return " ".join(lines)


def _saved_summary(state: DialogueState) -> str:
    return f"Saved — {describe(state)}."


def build_payload(state: DialogueState) -> dict[str, Any]:
    """
    The confirmed, typed payload for the writer.

    Deliberately a plain dict rather than a domain schema: this module stays
    free of database imports, and the writer is the layer that knows how to
    turn it into a `DailyLogSubmit` or a `VaccinationRecordCreate`.
    """
    return {
        "intent": state.intent.value,
        "slots": _jsonable(state.slots),
        "assumptions": list(state.assumptions),
    }
