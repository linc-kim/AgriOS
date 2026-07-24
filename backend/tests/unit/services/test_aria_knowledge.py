"""
ARIA knowledge base — retrieval behaviour.

The tests that matter here are the refusals. A knowledge base that answers
everything is worse than one that answers less and knows its edges: a confident
wrong husbandry answer costs a farmer real birds. So alongside the happy paths,
these pin that off-topic questions return nothing and that disease topics carry
the see-a-vet boundary required by §4.4.
"""

import pytest

from app.services import aria_knowledge as kb


class TestMatching:
    @pytest.mark.parametrize(
        "question,expected_key",
        [
            ("how do i vaccinate for newcastle?", "newcastle"),
            ("what is the difference between mareks and gumboro", "mareks"),
            ("how much water does a layer drink", "water_intake"),
            ("signs of coccidiosis", "coccidiosis"),
            ("feed formulation basics", "feed_basics"),
            ("what brooding temperature for chicks", "brooding_temperature"),
            ("lighting schedule for layers", "lighting"),
            ("how do i grade eggs", "egg_grading"),
            ("how to improve fcr", "fcr"),
            ("what is biosecurity", "biosecurity"),
        ],
    )
    def test_finds_the_right_topic(self, question, expected_key):
        answer = kb.answer(question)
        assert answer is not None, f"expected a match for {question!r}"
        assert answer["key"] == expected_key

    def test_gumboro_and_mareks_are_distinct(self):
        assert kb.answer("tell me about gumboro")["key"] == "gumboro"
        assert kb.answer("tell me about mareks disease")["key"] == "mareks"


class TestRefusals:
    @pytest.mark.parametrize(
        "question",
        [
            "what is the capital of kenya",
            "how do i fix my tractor engine",
            "write me a poem about chickens",
            "what were my egg sales last month",  # a data question, not knowledge
            "",
        ],
    )
    def test_off_topic_returns_nothing(self, question):
        """The whole point: no match rather than a padded guess."""
        assert kb.answer(question) is None

    def test_weak_overlap_does_not_match(self):
        """
        A stray shared word must not drag in an unrelated entry. "How is the
        weather today" shares 'today'-ish noise with nothing real.
        """
        assert kb.answer("how is the weather today") is None


class TestAnswerShape:
    def test_answer_has_the_required_fields(self):
        a = kb.answer("signs of coccidiosis")
        assert set(a) >= {
            "title", "explanation", "best_practices", "warnings",
            "source", "vet_now", "confidence",
        }
        assert a["explanation"]
        assert a["source"]

    def test_disease_topics_flag_vet_boundary(self):
        """
        §4.4: disease topics must send the farmer to a vet. The educational
        content explains the disease; it never concludes the farmer's birds
        have it, and the flag makes the boundary explicit.
        """
        for q in ("newcastle", "gumboro", "mareks", "coccidiosis"):
            assert kb.answer(q)["vet_now"] is True

    def test_husbandry_topics_do_not_overflag(self):
        # Non-urgent topics should not nag about a vet.
        for q in ("lighting schedule", "how to grade eggs", "feed formulation basics"):
            assert kb.answer(q)["vet_now"] is False


class TestTopics:
    def test_all_topics_listing(self):
        topics = kb.all_topics()
        assert len(topics) >= 10
        assert all({"key", "title", "category"} <= set(t) for t in topics)
