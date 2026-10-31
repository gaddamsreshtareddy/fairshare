import pytest

from logic.validators import ValidationError
from services import expense_service as es
from services import group_service as gs


@pytest.fixture
def setup(conn):
    g = gs.create_group(conn, "Trip", "INR")
    a, b, c = (gs.add_member(conn, g.id, n).id for n in "ABC")
    return g, a, b, c


def test_foreign_expense_is_converted(conn, setup):
    g, a, b, c = setup
    e = es.add_expense(conn, g.id, "Dinner", "Food", "2025-01-01",
                       payers={a: 1000}, split_method="equal", total=1000,
                       member_ids=[a, b, c], currency="USD", rate="83.25")
    assert e.currency == "USD"
    assert e.original_amount == 1000
    assert e.base_amount == 83250
    assert e.exchange_rate == 83.25
    assert sum(s.share_amount for s in e.splits) == 83250
    assert sum(p.amount_paid for p in e.payers) == 83250


def test_same_currency_needs_no_rate(conn, setup):
    g, a, b, c = setup
    e = es.add_expense(conn, g.id, "Dinner", "Food", "2025-01-01",
                       payers={a: 120000}, split_method="equal", total=120000,
                       member_ids=[a, b, c], currency="INR")
    assert e.base_amount == 120000
    assert e.exchange_rate == 1.0


def test_missing_rate_is_rejected_and_nothing_saved(conn, setup):
    g, a, b, c = setup
    with pytest.raises(ValidationError, match="exchange rate"):
        es.add_expense(conn, g.id, "Dinner", "Food", "2025-01-01",
                       payers={a: 1000}, split_method="equal", total=1000,
                       member_ids=[a, b, c], currency="USD")
    assert es.list_expenses(conn, g.id) == []


def test_unsupported_currency_is_rejected(conn, setup):
    g, a, b, c = setup
    with pytest.raises(ValidationError, match="not supported"):
        es.add_expense(conn, g.id, "Dinner", "Food", "2025-01-01",
                       payers={a: 1000}, split_method="equal", total=1000,
                       member_ids=[a, b, c], currency="JPY", rate="0.5")


def test_converted_item_expense_adds_up(conn, setup):
    g, a, b, c = setup
    e = es.add_expense(conn, g.id, "Party", "Food", "2025-01-01",
                       payers={a: 1000}, split_method="item",
                       items=[("Pizza", 600, [a, b]), ("Drinks", 400, [b, c])],
                       currency="USD", rate="83.25")
    assert e.base_amount == 83250
    assert sum(i.amount for i in e.items) == 83250
    assert sum(s.share_amount for s in e.splits) == 83250


def test_balances_still_sum_to_zero_after_conversion(conn, setup):
    g, a, b, c = setup
    es.add_expense(conn, g.id, "Taxi", "Transport", "2025-01-01",
                   payers={a: 700, b: 300}, split_method="equal", total=1000,
                   member_ids=[a, b, c], currency="EUR", rate="90.123")
    balances = es.get_balances(conn, g.id)
    assert sum(v["net"] for v in balances.values()) == 0