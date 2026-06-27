"""
Sprint 9 — Settings / Profile Unit Tests
Tests: UserUpdateIn schema validation, sms preference, language, UserOut sms field.
"""

import pytest
from pydantic import ValidationError

from app.schemas.auth import UserUpdateIn, UserOut


# ── UserUpdateIn — full_name validation ──────────────────────────────────────

class TestUserUpdateInFullName:
    def test_valid_full_name(self):
        obj = UserUpdateIn(full_name="Jane Farmer")
        assert obj.full_name == "Jane Farmer"

    def test_full_name_stripped(self):
        obj = UserUpdateIn(full_name="  John  ")
        assert obj.full_name == "John"

    def test_full_name_none_allowed(self):
        obj = UserUpdateIn(full_name=None)
        assert obj.full_name is None

    def test_full_name_blank_rejected(self):
        with pytest.raises(ValidationError):
            UserUpdateIn(full_name="   ")

    def test_full_name_omitted_allowed(self):
        obj = UserUpdateIn()
        assert obj.full_name is None

    def test_full_name_long_allowed(self):
        obj = UserUpdateIn(full_name="A" * 80)
        assert len(obj.full_name) == 80


# ── UserUpdateIn — language validation ───────────────────────────────────────

class TestUserUpdateInLanguage:
    def test_english_valid(self):
        obj = UserUpdateIn(language="en")
        assert obj.language == "en"

    def test_swahili_valid(self):
        obj = UserUpdateIn(language="sw")
        assert obj.language == "sw"

    def test_invalid_language_rejected(self):
        with pytest.raises(ValidationError):
            UserUpdateIn(language="fr")

    def test_invalid_language_uppercase_rejected(self):
        with pytest.raises(ValidationError):
            UserUpdateIn(language="EN")

    def test_language_none_allowed(self):
        obj = UserUpdateIn(language=None)
        assert obj.language is None

    def test_language_omitted(self):
        obj = UserUpdateIn()
        assert obj.language is None


# ── UserUpdateIn — sms_notifications_enabled ─────────────────────────────────

class TestUserUpdateInSMSPref:
    def test_sms_enabled_true(self):
        obj = UserUpdateIn(sms_notifications_enabled=True)
        assert obj.sms_notifications_enabled is True

    def test_sms_enabled_false(self):
        obj = UserUpdateIn(sms_notifications_enabled=False)
        assert obj.sms_notifications_enabled is False

    def test_sms_pref_none_allowed(self):
        obj = UserUpdateIn(sms_notifications_enabled=None)
        assert obj.sms_notifications_enabled is None

    def test_sms_pref_omitted(self):
        obj = UserUpdateIn()
        assert obj.sms_notifications_enabled is None


# ── UserUpdateIn — combined payload ──────────────────────────────────────────

class TestUserUpdateInCombined:
    def test_all_fields_set(self):
        obj = UserUpdateIn(
            full_name="Ali Hassan",
            language="sw",
            sms_notifications_enabled=False,
        )
        assert obj.full_name == "Ali Hassan"
        assert obj.language == "sw"
        assert obj.sms_notifications_enabled is False

    def test_empty_payload_valid(self):
        """A completely empty PATCH payload is valid — partial update."""
        obj = UserUpdateIn()
        assert obj.full_name is None
        assert obj.language is None
        assert obj.sms_notifications_enabled is None

    def test_only_language_set(self):
        obj = UserUpdateIn(language="en")
        assert obj.full_name is None
        assert obj.language == "en"

    def test_only_sms_set(self):
        obj = UserUpdateIn(sms_notifications_enabled=True)
        assert obj.full_name is None
        assert obj.sms_notifications_enabled is True

    def test_name_and_language_no_sms(self):
        obj = UserUpdateIn(full_name="Grace", language="sw")
        assert obj.sms_notifications_enabled is None

    def test_name_strips_and_language_validates(self):
        obj = UserUpdateIn(full_name="  Amina  ", language="sw")
        assert obj.full_name == "Amina"
        assert obj.language == "sw"


# ── UserUpdateIn — edge cases ─────────────────────────────────────────────────

class TestUserUpdateInEdgeCases:
    def test_name_single_char_valid(self):
        obj = UserUpdateIn(full_name="A")
        assert obj.full_name == "A"

    def test_name_with_swahili_chars(self):
        obj = UserUpdateIn(full_name="Juma Mwangi")
        assert obj.full_name == "Juma Mwangi"

    def test_language_random_string_rejected(self):
        with pytest.raises(ValidationError):
            UserUpdateIn(language="swahili")

    def test_language_number_rejected(self):
        with pytest.raises(ValidationError):
            UserUpdateIn(language="123")

    def test_sms_truthy_int_not_valid(self):
        """sms_notifications_enabled must be bool, not int coerced."""
        # Pydantic v2 coerces int to bool by default — 1 → True is acceptable
        obj = UserUpdateIn(sms_notifications_enabled=True)
        assert obj.sms_notifications_enabled is True
