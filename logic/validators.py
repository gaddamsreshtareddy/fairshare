"""Validation rules for FairShare (business logic layer).

Pure Python: no database, no Streamlit. Each validate_* function returns the
cleaned value, or raises ValidationError with a message safe to show the user.
"""

# Currencies FairShare supports (from the planning document).
SUPPORTED_CURRENCIES = ("INR", "USD", "EUR", "GBP", "AED")
CATEGORIES = ("Food", "Hotel", "Transport", "Entertainment", "Shopping", "Other")

MAX_GROUP_NAME_LENGTH = 50
MAX_MEMBER_NAME_LENGTH = 40


class ValidationError(ValueError):
    """Raised when user input is not acceptable.

    The message is written for the user, so the UI can show it directly.
    """


def clean_text(value) -> str:
    """Trim the text and collapse any run of spaces/tabs/newlines into one space.

    None becomes an empty string.
    """
    if value is None:
        return ""
    return " ".join(str(value).split())


def _validate_name(value, label: str, max_length: int) -> str:
    """Shared rule for names: required, and not longer than max_length."""
    cleaned = clean_text(value)
    if not cleaned:
        raise ValidationError(f"{label} is required.")
    if len(cleaned) > max_length:
        raise ValidationError(f"{label} must be at most {max_length} characters.")
    return cleaned


def validate_group_name(name) -> str:
    """Return the cleaned group name, or raise ValidationError."""
    return _validate_name(name, "Group name", MAX_GROUP_NAME_LENGTH)


def validate_member_name(name) -> str:
    """Return the cleaned member name, or raise ValidationError."""
    return _validate_name(name, "Member name", MAX_MEMBER_NAME_LENGTH)


def validate_currency(code) -> str:
    """Return the currency code in capitals, or raise ValidationError."""
    cleaned = clean_text(code).upper()
    if not cleaned:
        raise ValidationError("Currency is required.")
    if cleaned not in SUPPORTED_CURRENCIES:
        supported = ", ".join(SUPPORTED_CURRENCIES)
        raise ValidationError(
            f"Currency '{cleaned}' is not supported. Choose one of: {supported}."
        )
    return cleaned


MAX_AMOUNT = 100_000_000_00  # 10 crore rupees, in paise


def validate_amount(total, label="Amount"):
    """Total must be a whole number of paise, above 0 and not absurdly large."""
    if isinstance(total, bool) or not isinstance(total, int):
        raise ValidationError(f"{label} must be a whole number of paise.")
    if total <= 0:
        raise ValidationError(f"{label} must be greater than zero.")
    if total > MAX_AMOUNT:
        raise ValidationError(f"{label} is too large.")
    return total


def validate_expense_date(value):
    """Accept dates from 2000-01-01 up to one year from today."""
    from datetime import date, timedelta
    try:
        parsed = date.fromisoformat(str(value))
    except ValueError:
        raise ValidationError("Date is not valid.") from None
    if parsed < date(2000, 1, 1) or parsed > date.today() + timedelta(days=365):
        raise ValidationError("Date must be between 2000 and one year from today.")
    return parsed.isoformat()