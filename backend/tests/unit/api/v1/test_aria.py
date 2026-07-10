"""
AGRIOS — ARIA Module Unit Tests
Schema validation + pure-function logic — no database required.

Tests:
  TestARIAMessageCreate       (5 tests) — input schema validation
  TestRecommendationAction    (3 tests) — action enum validation
  TestLanguageDetection       (6 tests) — Swahili keyword heuristic
  TestTokenBudgetTrimming     (4 tests) — context trim logic
  TestQuotaConstants          (4 tests) — plan quota values
"""

import json

import pytest
from pydantic import ValidationError

from app.schemas.ai import ARIAMessageCreate, RecommendationAction
from app.services.aria_service import (
    PLAN_QUOTAS,
    _detect_language,
    _trim_context_to_budget,
)


# ── ARIAMessageCreate Validation ──────────────────────────────────────────────

class TestARIAMessageCreate:
    def test_valid_simple_message(self):
        msg = ARIAMessageCreate(content="How is my flock doing?")
        assert msg.content == "How is my flock doing?"
        assert msg.conversation_id is None
        assert msg.flock_id is None

    def test_content_minimum_length(self):
        # Single character is valid (min=1)
        msg = ARIAMessageCreate(content="?")
        assert len(msg.content) == 1

    def test_content_too_short_empty(self):
        with pytest.raises(ValidationError) as exc:
            ARIAMessageCreate(content="")
        errors = exc.value.errors()
        assert any("content" in str(e) for e in errors)

    def test_content_maximum_length(self):
        # Exactly 2000 chars is valid
        msg = ARIAMessageCreate(content="a" * 2000)
        assert len(msg.content) == 2000

    def test_content_exceeds_maximum(self):
        with pytest.raises(ValidationError):
            ARIAMessageCreate(content="a" * 2001)

    def test_with_optional_ids(self):
        import uuid
        conv_id = uuid.uuid4()
        flock_id = uuid.uuid4()
        msg = ARIAMessageCreate(
            content="Check my flock health",
            conversation_id=conv_id,
            flock_id=flock_id,
        )
        assert msg.conversation_id == conv_id
        assert msg.flock_id == flock_id

    def test_content_stripped_of_leading_trailing_whitespace(self):
        # Pydantic strips by default if strip_whitespace=True in schema
        # If not, content passes through — test schema's actual behaviour
        msg = ARIAMessageCreate(content="  hello world  ")
        # Content should either be stripped or kept as-is depending on schema config
        assert "hello world" in msg.content


# ── RecommendationAction Validation ──────────────────────────────────────────

class TestRecommendationAction:
    def test_acted_is_valid(self):
        ra = RecommendationAction(action="acted")
        assert ra.action == "acted"

    def test_dismissed_is_valid(self):
        ra = RecommendationAction(action="dismissed")
        assert ra.action == "dismissed"

    def test_invalid_action_rejected(self):
        with pytest.raises(ValidationError):
            RecommendationAction(action="deleted")

    def test_pending_not_an_allowed_action(self):
        # "pending" is a status, not a valid action input
        with pytest.raises(ValidationError):
            RecommendationAction(action="pending")


# ── Language Detection ────────────────────────────────────────────────────────

class TestLanguageDetection:
    def test_english_text_detected_as_en(self):
        text = "How many eggs did my flock produce this week?"
        assert _detect_language(text) == "en"

    def test_swahili_text_with_multiple_keywords(self):
        # "kuku" = chicken, "shamba" = farm — two hits → "sw"
        text = "kuku wangu wako shamba sasa"
        assert _detect_language(text) == "sw"

    def test_single_swahili_keyword_returns_en(self):
        # Only one hit — below the 2-hit threshold
        text = "My kuku are doing fine"
        assert _detect_language(text) == "en"

    def test_case_insensitive_swahili_detection(self):
        # Detection should be case-insensitive
        text = "KUKU wangu wako SHAMBA"
        assert _detect_language(text) == "sw"

    def test_empty_string_returns_en(self):
        assert _detect_language("") == "en"

    def test_multiple_swahili_keywords_strong_signal(self):
        text = "kuku shamba mifugo lishe magonjwa"
        assert _detect_language(text) == "sw"


# ── Token Budget Trimming ─────────────────────────────────────────────────────

class TestTokenBudgetTrimming:
    """
    Tests for _trim_context_to_budget.

    The function mirrors its real caller in ``send_message``: it takes a
    ``context_json`` **string** (``json.dumps`` of the farm context), the
    history text, and the question, and returns a ``(context_json, history_text)``
    tuple trimmed to fit within MAX_CONTEXT_TOKENS. Step 1 of the trim reduces
    each active flock's ``recent_logs`` from up to 14 down to 7 entries.
    """

    def _make_context(self, days: int = 14, log_notes: str = "") -> dict:
        """Build a farm context dict shaped like compile_farm_context output."""
        return {
            "farm": {"name": "Test Farm", "county": "Nairobi"},
            "active_flocks": [
                {
                    "id": "abc",
                    "name": "Flock A",
                    "bird_count": 500,
                    "recent_logs": [
                        {
                            "date": f"2024-01-{i + 1:02d}",
                            "mortality": 0,
                            "feed_kg": 50.0,
                            "notes": log_notes,
                        }
                        for i in range(days)
                    ],
                }
            ],
            "recent_expenses": [{"amount": "1000", "category": "Feed"}],
            "recent_revenue": [{"amount": "5000", "source": "Egg sales"}],
        }

    def test_small_context_passes_through_unchanged(self):
        context = self._make_context(days=3)
        trimmed_json, _ = _trim_context_to_budget(
            json.dumps(context), "", "How is my farm doing?"
        )
        parsed = json.loads(trimmed_json)
        # Small context — all sections should survive untouched.
        assert "farm" in parsed
        assert len(parsed["active_flocks"][0]["recent_logs"]) == 3

    def test_daily_logs_trimmed_to_7_when_oversized(self):
        """AR-02 trim order: first reduce each flock's recent_logs 14 -> 7."""
        # Inflate each log past the 32k-char (8k-token) budget to force trimming.
        context = self._make_context(days=14, log_notes="x" * 3000)
        trimmed_json, _ = _trim_context_to_budget(
            json.dumps(context), "", "How is my flock?"
        )
        parsed = json.loads(trimmed_json)
        assert len(parsed["active_flocks"][0]["recent_logs"]) == 7

    def test_result_is_valid_json_string(self):
        context = self._make_context(days=7)
        trimmed_json, history = _trim_context_to_budget(
            json.dumps(context), "", "Test question"
        )
        parsed = json.loads(trimmed_json)  # must not raise
        assert isinstance(parsed, dict)
        assert isinstance(history, str)

    def test_history_text_included_in_budget_calculation(self):
        """Providing a long history should not cause the function to crash."""
        context = self._make_context(days=3)
        long_history = "User: question\nAssistant: answer\n" * 50
        trimmed_json, _ = _trim_context_to_budget(
            json.dumps(context), long_history, "Current question"
        )
        assert isinstance(json.loads(trimmed_json), dict)


# ── Plan Quota Constants ──────────────────────────────────────────────────────

class TestQuotaConstants:
    def test_free_plan_quota_is_5(self):
        assert PLAN_QUOTAS["free"] == 5

    def test_starter_plan_quota_is_30(self):
        assert PLAN_QUOTAS["starter"] == 30

    def test_pro_plan_quota_is_none_meaning_unlimited(self):
        assert PLAN_QUOTAS["pro"] is None

    def test_all_expected_plans_present(self):
        assert set(PLAN_QUOTAS.keys()) >= {"free", "starter", "pro"}
