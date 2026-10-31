import pytest

from logic.currency import convert, needs_conversion, parse_rate
from logic.validators import ValidationError


def test_basic_conversion():
    assert convert(1000, "83.25") == 83250


def test_rate_of_one_changes_nothing():
    assert convert(12345, "1") == 12345


def test_half_rounds_up():
    assert convert(1, "0.5") == 1


def test_below_half_rounds_down():
    assert convert(1, "0.49") == 0


def test_zero_amount():
    assert convert(0, "83") == 0


def test_float_input_is_safe():
    assert convert(1000, 83.25) == 83250


@pytest.mark.parametrize("bad", ["abc", "", "0", "-5", "2000000", "NaN", "Infinity"])
def test_bad_rates_are_rejected(bad):
    with pytest.raises(ValidationError):
        parse_rate(bad)


def test_negative_amount_is_rejected():
    with pytest.raises(ValidationError):
        convert(-1, "83")


def test_needs_conversion():
    assert needs_conversion("USD", "INR") is True
    assert needs_conversion("INR", "INR") is False