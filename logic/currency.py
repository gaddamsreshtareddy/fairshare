"""Currency conversion (business logic layer). Pure Python: no network, no database.

Rate meaning: how many units of the BASE currency equal 1 unit of the
expense currency (for example USD -> INR is about 83).
All supported currencies have 2 decimals, so minor units convert directly.
"""

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from logic.validators import ValidationError

MAX_RATE = Decimal("1000000")


def parse_rate(value) -> Decimal:
    """Turn typed text or a number into a valid exchange rate (Decimal)."""
    try:
        rate = Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        raise ValidationError("Exchange rate must be a number.") from None
    if not rate.is_finite():
        raise ValidationError("Exchange rate must be a number.")
    if rate <= 0:
        raise ValidationError("Exchange rate must be greater than zero.")
    if rate > MAX_RATE:
        raise ValidationError("Exchange rate is too large.")
    return rate


def convert(amount_minor: int, rate) -> int:
    """Convert minor units to base-currency minor units, rounding half up."""
    if amount_minor < 0:
        raise ValidationError("Amount cannot be negative.")
    converted = Decimal(amount_minor) * parse_rate(rate)
    return int(converted.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def needs_conversion(expense_currency: str, base_currency: str) -> bool:
    """True when the expense is in a different currency from the group's base."""
    return expense_currency != base_currency