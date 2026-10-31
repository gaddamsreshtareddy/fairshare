from decimal import Decimal

import pytest
import requests

from logic.validators import ValidationError
from services.rate_service import fetch_rate


class FakeResponse:
    def __init__(self, payload=None, status_ok=True, bad_json=False):
        self.payload, self.status_ok, self.bad_json = payload, status_ok, bad_json

    def raise_for_status(self):
        if not self.status_ok:
            raise requests.HTTPError("500")

    def json(self):
        if self.bad_json:
            raise ValueError("not json")
        return self.payload


def fake_get(response):
    return lambda url, timeout: response


def test_successful_fetch():
    get = fake_get(FakeResponse({"rates": {"INR": 83.25}}))
    assert fetch_rate("USD", "INR", get=get) == Decimal("83.25")


def test_same_currency_needs_no_network():
    def boom(url, timeout):
        raise AssertionError("network must not be called")
    assert fetch_rate("INR", "INR", get=boom) == Decimal(1)


def test_missing_currency_in_response():
    with pytest.raises(ValidationError, match="type the rate manually"):
        fetch_rate("USD", "INR", get=fake_get(FakeResponse({"rates": {}})))


def test_http_error():
    with pytest.raises(ValidationError, match="type the rate manually"):
        fetch_rate("USD", "INR", get=fake_get(FakeResponse(status_ok=False)))


def test_connection_error():
    def down(url, timeout):
        raise requests.ConnectionError("offline")
    with pytest.raises(ValidationError, match="type the rate manually"):
        fetch_rate("USD", "INR", get=down)


def test_invalid_json():
    with pytest.raises(ValidationError, match="type the rate manually"):
        fetch_rate("USD", "INR", get=fake_get(FakeResponse(bad_json=True)))


def test_nonsense_rate_value_is_rejected():
    with pytest.raises(ValidationError):
        fetch_rate("USD", "INR", get=fake_get(FakeResponse({"rates": {"INR": -5}})))