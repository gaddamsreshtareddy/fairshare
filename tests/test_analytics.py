from data.models import Expense
from logic.analytics import (
    spending_by_category,
    spending_by_date,
    top_category,
    top_contributor,
    top_spender,
)


def exp(category, amount, day="2025-01-01"):
    return Expense(id=None, group_id=1, title="x", expense_date=day, currency="INR",
                   original_amount=amount, base_amount=amount,
                   split_method="equal", category=category)


EXPENSES = [exp("Food", 1000), exp("Hotel", 5000, "2025-01-02"),
            exp("Food", 2000, "2025-01-02"), exp("Transport", 500)]


def test_spending_by_category_sorted_biggest_first():
    result = spending_by_category(EXPENSES)
    assert result == {"Hotel": 5000, "Food": 3000, "Transport": 500}
    assert list(result)[0] == "Hotel"


def test_spending_by_date_oldest_first():
    assert spending_by_date(EXPENSES) == {"2025-01-01": 1500, "2025-01-02": 7000}


def test_top_category():
    assert top_category(EXPENSES) == ("Hotel", 5000)


def test_empty_inputs_give_none_or_empty():
    assert spending_by_category([]) == {}
    assert top_category([]) is None
    assert top_contributor({}) is None
    assert top_spender({1: {"paid": 0, "owed": 0, "net": 0}}) is None


BALANCES = {1: {"paid": 9000, "owed": 3000, "net": 6000},
            2: {"paid": 0, "owed": 4000, "net": -4000},
            3: {"paid": 0, "owed": 2000, "net": -2000}}


def test_top_contributor_is_who_paid_most():
    assert top_contributor(BALANCES) == (1, 9000)


def test_top_spender_is_who_owes_most():
    assert top_spender(BALANCES) == (2, 4000)


def test_ties_go_to_smaller_member_id():
    tied = {5: {"paid": 100, "owed": 0, "net": 100},
            2: {"paid": 100, "owed": 0, "net": 100}}
    assert top_contributor(tied) == (2, 100)