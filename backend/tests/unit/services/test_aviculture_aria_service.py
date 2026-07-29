"""
Aviculture ARIA — the deterministic guards & answerers (Module 15, Part 10).

ARIA explains; it never calculates or diagnoses. These tests lock the frozen
guarantees that don't need a database or an LLM: the disease-diagnosis ban,
deterministic factual answers drawn only from recorded facts (honesty-labelled),
the offline grounded summary, and the 150-word cap.
"""

from app.services import aviculture_aria_service as a


CTX = {
    "farm": "Demo", "birds_total": 4, "by_species": {"African Grey": 4},
    "by_status": {"active": 3, "sold": 1}, "active_pairs": 1, "active_breeding_programs": 0,
    "active_incubation_batches": 1, "hatch_rate_pct": {"value": 60.0, "label": "calculated"},
    "mortality_rate_pct": {"value": None, "label": "unknown"},
    "vaccination_coverage_pct": {"value": 50.0, "label": "calculated"},
    "active_quarantines": 0, "active_disease_events": 0,
    "collection_value": {"value": 120000.0, "label": "recorded_fact"}, "tasks_due": 3,
}


class TestDiagnosisBan:
    def test_diagnosis_intents_detected(self):
        for q in ["Diagnose my macaw", "what disease does my bird have?",
                  "what's wrong with my parrot medically", "what is the cure for this"]:
            assert a._is_diagnosis(q) is True

    def test_normal_questions_not_flagged(self):
        for q in ["how many birds do I have", "explain incubation", "tell me about African Greys"]:
            assert a._is_diagnosis(q) is False


class TestFactualAnswers:
    def test_bird_count_is_recorded_fact(self):
        ans, ftype, src = a._factual_answer("how many birds do I have", CTX)
        assert "4 bird" in ans and ftype == a.RECORDED and src == ["collection.total"]

    def test_pairs(self):
        ans, ftype, _ = a._factual_answer("how many breeding pairs", CTX)
        assert "1 active breeding pair" in ans and ftype == a.RECORDED

    def test_collection_value(self):
        ans, ftype, _ = a._factual_answer("what is my collection worth", CTX)
        assert "120000" in ans and ftype == a.RECORDED

    def test_missing_mortality_is_unavailable_not_fabricated(self):
        ans, ftype, _ = a._factual_answer("what is my mortality rate", CTX)
        assert ftype == a.UNAVAILABLE and "Not enough recorded data" in ans

    def test_tasks_due(self):
        ans, ftype, _ = a._factual_answer("what tasks are due", CTX)
        assert "3 operational task" in ans and ftype == a.CALCULATED

    def test_open_question_returns_none(self):
        assert a._factual_answer("explain line breeding to me", CTX) is None


class TestOfflineAndCap:
    def test_offline_summary_is_grounded(self):
        s = a._summary_offline(CTX)
        assert "4 bird" in s and "1 active pair" in s and "never guess" in s.lower()

    def test_word_cap(self):
        long = " ".join(["word"] * 400)
        assert len(a._clamp_words(long).split()) <= a._MAX_WORDS + 1  # +1 for the ellipsis token

    def test_prompt_contains_facts_and_rules(self):
        p = a._build_prompt("explain incubation", CTX, None)
        assert "NEVER diagnose disease" in p and "under 150 words" in p and "birds_total" in p
