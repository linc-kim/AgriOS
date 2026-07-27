"""
ARIA language identification.

A trilingual farm writes in English, Swahili and Sheng, often in one breath. The
classifier only needs to identify the primary language and whether the sentence
is mixed — enough for the router to choose a path and for ARIA to reply in kind —
so these tests pin the examples from the spec and the mixed-sentence behaviour.
"""

from app.services.aria_language import Language, detect_language, reply_language_note


class TestPrimaryLanguage:
    def test_plain_english(self):
        assert detect_language("How many birds died this month?").primary is Language.ENGLISH

    def test_plain_swahili(self):
        assert detect_language("Kuku wangu wameanza kutaga mayai").primary is Language.SWAHILI

    def test_spec_swahili_examples(self):
        assert detect_language("Egg production ilikuwa 432").primary in (Language.ENGLISH, Language.SWAHILI)
        assert detect_language("Nimepea layers kilo 45 leo").primary in (Language.SWAHILI, Language.SHENG)

    def test_sheng_markers_shift_primary(self):
        r = detect_language("Niaje buda, kuku wako poa?")
        assert r.primary is Language.SHENG

    def test_empty_defaults_to_english(self):
        assert detect_language("").primary is Language.ENGLISH


class TestMixed:
    def test_mixed_english_swahili(self):
        r = detect_language("Remind me kesho nioshe drinkers")
        assert r.mixed is True

    def test_pure_english_not_mixed(self):
        assert detect_language("Record 45 kg of feed today").mixed is False


class TestTransparency:
    def test_scores_and_evidence_exposed(self):
        r = detect_language("Nimepea kuku chakula leo")
        assert set(r.scores) == {"en", "sw", "sheng"}
        assert r.scores["sw"] > 0
        assert r.evidence["sw"]

    def test_languages_list_primary_first(self):
        r = detect_language("Remind me kesho")
        assert r.languages[0] == r.primary.value


class TestReplyNote:
    def test_reply_note_matches_language(self):
        assert "Swahili" in reply_language_note(detect_language("Kuku wangu wanaumwa"))
        assert "English" in reply_language_note(detect_language("How is my flock doing today"))
