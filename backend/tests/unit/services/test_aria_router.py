"""
ARIA AI router — the deterministic-first decision engine.

The router is the one place the Part 8 honesty rules become checkable rather than
hoped for, so these tests weigh it heavily: structured farm work must route to a
deterministic engine and never to Gemini; report explanations and simulations may
only hand Gemini finished output to rephrase; disease language always attaches the
no-diagnosis rule; out-of-scope species are declined without a model; and turning
AI off must force every would-be Gemini route to a deterministic/offline one.
"""


from app.services import aria_router as r
from app.services.aria_router import Attachment, Engine, RouteTarget, Safety


def route(text, **kw):
    return r.route(text, **kw)


class TestDeterministicFirst:
    def test_record_is_deterministic(self):
        d = route("Egg production ilikuwa 432")
        assert d.target is RouteTarget.RECORD
        assert d.engine is Engine.DETERMINISTIC
        assert d.needs_gemini is False

    def test_multilingual_feed_record(self):
        d = route("Nimepea layers kilo 45 leo")
        assert d.target is RouteTarget.RECORD
        assert d.needs_gemini is False

    def test_farm_chat_is_deterministic(self):
        for q in ("How many birds died this month?", "Which flock performs best?",
                  "What reminders are overdue?"):
            d = route(q)
            assert d.target is RouteTarget.FARM_CHAT, q
            assert d.engine is Engine.DETERMINISTIC
            assert d.needs_gemini is False

    def test_knowledge_is_deterministic(self):
        d = route("How do I vaccinate against Newcastle?")
        assert d.target is RouteTarget.KNOWLEDGE
        assert d.needs_gemini is False


class TestGeminiOnlyWhenNeeded:
    def test_general_chat_uses_gemini(self):
        d = route("Tell me a story about farming in Kenya")
        assert d.target is RouteTarget.GENERAL_CHAT
        assert d.engine is Engine.GEMINI
        assert d.needs_gemini is True

    def test_report_explain_is_hybrid_not_calculation(self):
        d = route("Explain this health report")
        assert d.target is RouteTarget.REPORT_EXPLAIN
        assert d.engine is Engine.HYBRID
        assert Safety.NO_CALC_TO_GEMINI in d.safety

    def test_simulation_is_hybrid_not_calculation(self):
        d = route("What happens if feed prices double?")
        assert d.target is RouteTarget.SIMULATION
        assert d.engine is Engine.HYBRID
        assert Safety.NO_CALC_TO_GEMINI in d.safety


class TestAiDisabledForcesDeterministic:
    def test_general_chat_offline_when_disabled(self):
        d = route("Tell me a story", ai_enabled=False)
        assert d.needs_gemini is False
        assert d.engine is Engine.DETERMINISTIC

    def test_explain_offline_when_disabled(self):
        d = route("Explain this report", ai_enabled=False)
        assert d.needs_gemini is False
        assert d.engine is Engine.DETERMINISTIC


class TestSafety:
    def test_health_symptom_attaches_no_diagnosis(self):
        d = route("Broilers wameanza kukohoa")
        assert Safety.NO_DIAGNOSIS in d.safety

    def test_english_symptom_attaches_no_diagnosis(self):
        d = route("My birds are coughing and not eating")
        assert Safety.NO_DIAGNOSIS in d.safety

    def test_every_decision_is_permission_scoped(self):
        for q in ("Egg production 432", "Explain report", "Tell me a joke", "Ngombe"):
            assert Safety.PERMISSION_SCOPED in route(q).safety


class TestOutOfScope:
    def test_cattle_declined_deterministically(self):
        d = route("How much milk do my ngombe produce?")
        assert d.target is RouteTarget.OUT_OF_SCOPE
        assert d.needs_gemini is False

    def test_goats_declined(self):
        assert route("My mbuzi are sick").target is RouteTarget.OUT_OF_SCOPE

    def test_poultry_record_not_declined_even_with_scope_word(self):
        # "Sold 40 birds and 2 goats" — a poultry record should still record.
        d = route("Sold 40 birds today")
        assert d.target is RouteTarget.RECORD


class TestAttachments:
    def test_image_routes_to_vision_with_no_diagnosis(self):
        d = route("what's wrong with this bird", attachments=[Attachment("bird.jpg", "image/jpeg", 100)])
        assert d.target is RouteTarget.VISION
        assert d.needs_gemini is True
        assert Safety.NO_DIAGNOSIS in d.safety

    def test_csv_routes_to_deterministic_extract(self):
        d = route("here are my purchases", attachments=[Attachment("feed.csv", "text/csv", 100)])
        assert d.target is RouteTarget.DOCUMENT_EXTRACT
        assert d.engine is Engine.DETERMINISTIC
        assert d.needs_gemini is False

    def test_xlsx_is_deterministic(self):
        d = route("", attachments=[Attachment("data.xlsx", "application/vnd.openxmlformats", 100)])
        assert d.target is RouteTarget.DOCUMENT_EXTRACT

    def test_pdf_routes_to_gemini(self):
        d = route("summarise this", attachments=[Attachment("manual.pdf", "application/pdf", 100)])
        assert d.target is RouteTarget.DOCUMENT_AI
        assert d.needs_gemini is True


class TestLanguageCarried:
    def test_language_is_reported(self):
        assert route("Nimepea kuku chakula").language.primary.value in ("sw", "sheng")
        assert route("How many birds died?").language.primary.value == "en"

    def test_determinism(self):
        a = route("What happens if feed prices double?")
        b = route("What happens if feed prices double?")
        assert (a.target, a.engine, a.needs_gemini) == (b.target, b.engine, b.needs_gemini)
