"""
ARIA reverse interviewing — conversation behaviour.

The parser's tests pin what a sentence means. These pin what ARIA *does* about
it: what it asks, when it refuses to save, and what payload comes out the far
end. The central guarantee under test is that nothing reaches `READY` until
every required slot is present and the farmer has said yes.
"""

from datetime import date
from decimal import Decimal

import pytest

from app.services.aria_dialogue import (
    DialogueState,
    Stage,
    advance,
    begin,
    build_payload,
    interpret_yes_no,
    is_skip,
)
from app.services.aria_nlu import Intent, parse

TODAY = date(2026, 7, 22)


def open_conversation(text: str):
    """Parse an opening line and take the first turn."""
    state = begin(parse(text, today=TODAY))
    return advance(state, None, today=TODAY)


class TestYesNo:
    @pytest.mark.parametrize("text", ["yes", "Yeah", "ok", "save", "ndio", "yes save it"])
    def test_affirmative(self, text):
        assert interpret_yes_no(text) is True

    @pytest.mark.parametrize("text", ["no", "Nope", "cancel", "hapana", "no thats wrong"])
    def test_negative(self, text):
        assert interpret_yes_no(text) is False

    def test_ambiguous_is_none(self):
        assert interpret_yes_no("flock 2") is None

    def test_confirmation_card_option_labels(self):
        """
        The workspace renders "Yes, save it" / "No, cancel" as the confirm
        buttons and sends the label verbatim. The comma after the first word
        must not defeat detection, or tapping the save button does nothing.
        """
        assert interpret_yes_no("Yes, save it") is True
        assert interpret_yes_no("No, cancel") is False

    def test_skip_detection(self):
        assert is_skip("skip")
        assert is_skip("not sure")
        assert is_skip("sijui")
        assert not is_skip("flock 2")


class TestMortalityInterview:
    def test_asks_for_flock_when_not_given(self):
        """
        The headline case. "Three birds died" is not recordable until we know
        which flock — guessing would attach the loss to the wrong birds.
        """
        state, reply = open_conversation("three birds died this morning")
        assert state.stage is Stage.COLLECTING
        assert state.pending == "flock_ref"
        assert "which flock" in reply.text.lower()

    def test_does_not_reach_ready_while_flock_missing(self):
        state, _ = open_conversation("three birds died")
        assert state.stage is not Stage.READY

    def test_answering_flock_moves_to_probing(self):
        state, _ = open_conversation("three birds died this morning")
        state, reply = advance(state, "flock 2", today=TODAY)
        assert state.slots["flock_ref"] == "2"
        # Count and flock are both known now, so it probes for clinical context.
        assert state.stage is Stage.PROBING

    def test_probes_then_confirms(self):
        state, _ = open_conversation("three birds died this morning")
        state, _ = advance(state, "flock 2", today=TODAY)
        for _ in range(3):
            if state.stage is Stage.PROBING:
                state, reply = advance(state, "skip", today=TODAY)
        assert state.stage is Stage.CONFIRMING
        assert "save" in reply.text.lower()

    def test_probe_answers_are_captured(self):
        state, _ = open_conversation("three birds died")
        state, _ = advance(state, "flock 2", today=TODAY)
        state, _ = advance(state, "they were coughing", today=TODAY)
        assert "coughing" in str(state.slots.get("symptoms", "")).lower()

    def test_confirmation_saves(self):
        state, _ = open_conversation("three birds died this morning")
        state, _ = advance(state, "flock 2", today=TODAY)
        for _ in range(3):
            if state.stage is Stage.PROBING:
                state, _ = advance(state, "skip", today=TODAY)
        state, reply = advance(state, "yes", today=TODAY)
        assert state.stage is Stage.READY
        assert reply.payload is not None
        assert reply.payload["slots"]["count"] == 3
        assert reply.payload["slots"]["flock_ref"] == "2"

    def test_declining_cancels_without_writing(self):
        state, _ = open_conversation("three birds died")
        state, _ = advance(state, "flock 2", today=TODAY)
        for _ in range(3):
            if state.stage is Stage.PROBING:
                state, _ = advance(state, "skip", today=TODAY)
        state, reply = advance(state, "no", today=TODAY)
        assert state.stage is Stage.CANCELLED
        assert reply.payload is None
        assert "haven't saved" in reply.text.lower()


class TestCompleteUtterances:
    def test_fully_specified_mortality_still_confirms(self):
        """
        Even a complete sentence gets a confirmation step. Nothing reaches the
        database without the farmer seeing it first.
        """
        state, reply = open_conversation("we lost 2 birds in flock 3 yesterday")
        # Required slots are all present, so it goes straight to probing.
        assert state.stage in (Stage.PROBING, Stage.CONFIRMING)
        assert state.stage is not Stage.READY

    def test_egg_count_skips_probes(self):
        """
        Egg collection is not probed — the questions that matter for mortality
        are noise here, and noise is what makes farmers stop using it.
        """
        state, reply = open_conversation("collected 945 eggs from flock 2 today")
        assert state.stage is Stage.CONFIRMING
        assert "945" in reply.text

    def test_vaccination_asks_only_for_what_is_missing(self):
        state, reply = open_conversation("we vaccinated newcastle today")
        assert state.pending == "flock_ref"
        state, reply = advance(state, "flock 1", today=TODAY)
        # Vaccine and flock known; route is a probe but vaccination is not
        # probed, so it confirms.
        assert state.stage is Stage.CONFIRMING
        assert "Newcastle" in reply.text


class TestWeighIn:
    def test_asks_for_each_missing_measurement_in_turn(self):
        state, reply = open_conversation("we weighed the birds today")
        assert state.pending == "flock_ref"
        state, reply = advance(state, "flock 2", today=TODAY)
        assert state.pending == "sample_size"
        state, reply = advance(state, "20", today=TODAY)
        assert state.pending == "average_weight_kg"
        state, reply = advance(state, "1.8 kg", today=TODAY)
        assert state.stage is Stage.CONFIRMING
        assert state.slots["sample_size"] == 20
        assert state.slots["average_weight_kg"] == Decimal("1.8")


class TestFeedPurchase:
    def test_asks_for_cost_when_only_quantity_given(self):
        state, reply = open_conversation("i bought 12 bags of growers mash")
        assert state.pending == "amount"
        assert "cost" in reply.text.lower()

    def test_completes_with_cost(self):
        state, _ = open_conversation("i bought 12 bags of growers mash")
        state, reply = advance(state, "39000", today=TODAY)
        assert state.stage is Stage.CONFIRMING
        assert state.slots["quantity_kg"] == Decimal(600)
        assert state.slots["amount"] == Decimal(39000)

    def test_assumption_about_bag_size_is_surfaced(self):
        state, _ = open_conversation("i bought 12 bags of feed")
        state, reply = advance(state, "39000", today=TODAY)
        assert any("50" in a for a in state.assumptions)
        assert "50" in reply.text


class TestTopicChange:
    def test_switching_intent_abandons_the_draft(self):
        """
        A farmer who starts recording mortality and then asks about eggs has
        moved on. Silently attaching the new answer to the old draft would
        record something they never said.
        """
        state, _ = open_conversation("three birds died")
        state, reply = advance(state, "collected 900 eggs in flock 1", today=TODAY)
        assert state.stage is Stage.ABANDONED
        assert reply.payload is None

    def test_answer_to_a_pending_question_is_not_a_topic_change(self):
        state, _ = open_conversation("three birds died")
        assert state.pending == "flock_ref"
        state, _ = advance(state, "flock 2", today=TODAY)
        assert state.stage is not Stage.ABANDONED

    def test_explicit_cancel(self):
        state, _ = open_conversation("three birds died")
        state, reply = advance(state, "cancel", today=TODAY)
        assert state.stage is Stage.CANCELLED
        assert reply.payload is None


class TestStatePersistence:
    def test_round_trips_through_json(self):
        """
        State lives on the conversation row between turns, so it has to survive
        serialisation with its types intact — a date that comes back as a
        string would be written to the database as the wrong type.
        """
        state, _ = open_conversation("we lost 2 birds in flock 3 yesterday")
        restored = DialogueState.from_dict(state.to_dict())
        assert restored.intent is Intent.RECORD_MORTALITY
        assert restored.slots["count"] == 2
        assert restored.slots["flock_ref"] == "3"
        assert restored.slots["date"] == date(2026, 7, 21)
        assert restored.stage is state.stage

    def test_decimal_slots_survive_round_trip(self):
        state, _ = open_conversation("i bought 12 bags of feed")
        state, _ = advance(state, "39000", today=TODAY)
        restored = DialogueState.from_dict(state.to_dict())
        assert restored.slots["quantity_kg"] == Decimal(600)
        assert isinstance(restored.slots["amount"], Decimal)


class TestPayload:
    def test_payload_contains_only_stated_facts(self):
        state, _ = open_conversation("three birds died this morning")
        state, _ = advance(state, "flock 2", today=TODAY)
        for _ in range(3):
            if state.stage is Stage.PROBING:
                state, _ = advance(state, "skip", today=TODAY)
        state, _ = advance(state, "yes", today=TODAY)
        payload = build_payload(state)
        assert payload["intent"] == "record_mortality"
        assert payload["slots"]["count"] == 3
        # Nothing clinical was volunteered, so nothing clinical is claimed.
        assert "symptoms" not in payload["slots"]
