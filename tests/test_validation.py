"""Tests for the validation rules (logic/validators.py)."""

import pytest

from logic.validators import (
    SUPPORTED_CURRENCIES,
    ValidationError,
    clean_text,
    validate_currency,
    validate_group_name,
    validate_member_name,
    validate_amount, 
    validate_expense_date
)


# ---------------------------------------------------------------------------
# clean_text
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("raw, expected", [
    ("  Goa   Trip ", "Goa Trip"),
    ("Ravi", "Ravi"),
    ("a\tb\nc", "a b c"),
    (None, ""),
])
def test_clean_text(raw, expected):
    assert clean_text(raw) == expected


# ---------------------------------------------------------------------------
# Group names
# ---------------------------------------------------------------------------
def test_group_name_is_cleaned_and_returned():
    assert validate_group_name("  Goa   Trip  ") == "Goa Trip"


@pytest.mark.parametrize("blank", ["", "   ", None, "\t\n"])
def test_blank_group_name_is_rejected(blank):
    with pytest.raises(ValidationError, match="Group name is required"):
        validate_group_name(blank)


def test_group_name_length_limit():
    assert validate_group_name("a" * 50) == "a" * 50      # exactly 50 is fine
    with pytest.raises(ValidationError, match="at most 50"):
        validate_group_name("a" * 51)                      # 51 is too long


# ---------------------------------------------------------------------------
# Member names
# ---------------------------------------------------------------------------
def test_member_name_is_cleaned_and_returned():
    assert validate_member_name("  Ravi   Kumar ") == "Ravi Kumar"


@pytest.mark.parametrize("blank", ["", "   ", None, "\t\n"])
def test_blank_member_name_is_rejected(blank):
    with pytest.raises(ValidationError, match="Member name is required"):
        validate_member_name(blank)


def test_member_name_length_limit():
    assert validate_member_name("a" * 40) == "a" * 40
    with pytest.raises(ValidationError, match="at most 40"):
        validate_member_name("a" * 41)


# ---------------------------------------------------------------------------
# Currency
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("raw, expected", [
    ("inr", "INR"),
    (" usd ", "USD"),
    ("Eur", "EUR"),
])
def test_currency_is_normalised_to_capitals(raw, expected):
    assert validate_currency(raw) == expected


@pytest.mark.parametrize("code", SUPPORTED_CURRENCIES)
def test_every_supported_currency_is_accepted(code):
    assert validate_currency(code) == code


@pytest.mark.parametrize("bad", ["JPY", "RUPEES", "", None, "  "])
def test_unsupported_or_missing_currency_is_rejected(bad):
    with pytest.raises(ValidationError):
        validate_currency(bad)


def test_unsupported_currency_message_lists_the_choices():
    with pytest.raises(ValidationError, match="not supported.*INR"):
        validate_currency("JPY")


# ---------------------------------------------------------------------------
# The error type itself
# ---------------------------------------------------------------------------
def test_validation_error_is_a_value_error():
    assert issubclass(ValidationError, ValueError)


from datetime import date, timedelta


def test_amount_rules():
    assert validate_amount(100) == 100
    for bad in (0, -5, 12.5, "100", True, 100_000_000_01):
        with pytest.raises(ValidationError):
            validate_amount(bad)


def test_date_rules():
    assert validate_expense_date("2025-01-31") == "2025-01-31"
    assert validate_expense_date(date.today()) == date.today().isoformat()
    for bad in ("2025-13-45", "1999-12-31", "abc",
                (date.today() + timedelta(days=400)).isoformat()):
        with pytest.raises(ValidationError):
            validate_expense_date(bad)