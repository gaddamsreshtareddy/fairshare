"""Live exchange-rate lookup (application layer).

Uses a free public API (no key). If anything goes wrong, a ValidationError
is raised and the user types the rate manually instead.
"""

from decimal import Decimal

import requests

from logic.currency import parse_rate
from logic.validators import ValidationError

API_URL = "https://open.er-api.com/v6/latest/{base}"


def fetch_rate(from_currency, to_currency, get=requests.get, timeout=5) -> Decimal:
    """Return how many `to_currency` units equal 1 `from_currency`.

    `get` can be replaced in tests so no real network call is made.
    """
    if from_currency == to_currency:
        return Decimal(1)
    try:
        response = get(API_URL.format(base=from_currency), timeout=timeout)
        response.raise_for_status()
        value = response.json()["rates"][to_currency]
    except (requests.RequestException, ValueError, KeyError, TypeError):
        raise ValidationError(
            "Could not fetch a live rate. Please type the rate manually."
        ) from None
    return parse_rate(value)