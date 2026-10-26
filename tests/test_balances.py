from data.models import Expense, PayerShare, Split
from logic.balances import calculate_balances


def make_expense(payers, splits, title="Test"):
    """Build an Expense from {member_id: paise} dicts for payers and splits."""
    total = sum(payers.values())
    return Expense(
        id=None, group_id=1, title=title, expense_date="2025-01-01",
        currency="INR", original_amount=total, base_amount=total,
        split_method="custom",
        payers=[PayerShare(member_id=m, amount_paid=a) for m, a in payers.items()],
        splits=[Split(member_id=m, share_amount=a) for m, a in splits.items()],
    )

def test_dinner_one_payer_equal_split():
    dinner = make_expense({1: 120000}, {1: 40000, 2: 40000, 3: 40000})
    result = calculate_balances([dinner], [1, 2, 3])
    assert result[1] == {"paid": 120000, "owed": 40000, "net": 80000}
    assert result[2]["net"] == -40000
    assert result[3]["net"] == -40000

def test_two_payers():
    expense = make_expense({1: 70000, 2: 50000}, {1: 40000, 2: 40000, 3: 40000})
    result = calculate_balances([expense], [1, 2, 3])
    assert result[1]["net"] == 30000
    assert result[2]["net"] == 10000
    assert result[3]["net"] == -40000


def test_several_expenses_add_up():
    dinner = make_expense({1: 120000}, {1: 40000, 2: 40000, 3: 40000})
    snacks = make_expense({2: 30000}, {2: 15000, 3: 15000})
    result = calculate_balances([dinner, snacks], [1, 2, 3])
    assert result[1]["net"] == 80000
    assert result[2]["net"] == -25000
    assert result[3]["net"] == -55000


def test_unused_member_appears_with_zeros():
    dinner = make_expense({1: 120000}, {1: 40000, 2: 40000, 3: 40000})
    result = calculate_balances([dinner], [1, 2, 3, 4])
    assert result[4] == {"paid": 0, "owed": 0, "net": 0}


def test_no_expenses():
    result = calculate_balances([], [1, 2, 3])
    assert all(v == {"paid": 0, "owed": 0, "net": 0} for v in result.values())


def test_nets_always_sum_to_zero():
    dinner = make_expense({1: 120000}, {1: 40000, 2: 40000, 3: 40000})
    snacks = make_expense({2: 30000}, {2: 15000, 3: 15000})
    result = calculate_balances([dinner, snacks], [1, 2, 3])
    assert sum(v["net"] for v in result.values()) == 0