import pytest

from logic.settlement_algorithm import exact_settlement, greedy_settlement, settle
from logic.validators import ValidationError


def apply(balances, payments):
    """Apply the payments to the balances and return the result."""
    result = dict(balances)
    for payer, receiver, amount in payments:
        result[payer] += amount
        result[receiver] -= amount
    return result


def test_simple_pair():
    assert greedy_settlement({1: 5000, 2: -5000}) == [(2, 1, 5000)]


def test_three_people_example():
    balances = {1: 80000, 2: -25000, 3: -55000}
    payments = greedy_settlement(balances)
    assert payments == [(3, 1, 55000), (2, 1, 25000)]
    assert all(v == 0 for v in apply(balances, payments).values())


def test_everyone_settled():
    assert greedy_settlement({1: 0, 2: 0}) == []


def test_empty():
    assert greedy_settlement({}) == []


def test_zero_balance_member_is_ignored():
    payments = greedy_settlement({1: 100, 2: -100, 3: 0})
    assert all(3 not in (p[0], p[1]) for p in payments)


def test_unbalanced_input_is_rejected():
    with pytest.raises(ValidationError, match="add up to zero"):
        greedy_settlement({1: 100, 2: -50})


def test_no_payment_is_zero_or_negative():
    payments = greedy_settlement({1: 700, 2: 300, 3: -400, 4: -600})
    assert all(amount > 0 for _, _, amount in payments)


def test_payment_count_limit():
    balances = {1: 900, 2: 100, 3: -250, 4: -350, 5: -400}  # 5 people
    assert len(greedy_settlement(balances)) <= 4


@pytest.mark.parametrize("balances", [
    {1: 80000, 2: -25000, 3: -55000},
    {1: 700, 2: 300, 3: -400, 4: -600},
    {1: 1, 2: 1, 3: 1, 4: -3},
    {1: 5, 2: 3, 3: 4, 4: -5, 5: -7},
])
def test_everyone_ends_at_zero(balances):
    payments = greedy_settlement(balances)
    assert all(v == 0 for v in apply(balances, payments).values())


def test_greedy_is_not_always_minimal():
    # {+5, -5} and {+3, +4, -7} are two separate groups: 1 + 2 = 3 payments is
    # possible, but greedy uses 4. This is why Step 6.2 adds the exact method.
    balances = {1: 5, 2: 3, 3: 4, 4: -5, 5: -7}
    assert len(greedy_settlement(balances)) == 4


CASES = [
    {1: 80000, 2: -25000, 3: -55000},
    {1: 700, 2: 300, 3: -400, 4: -600},
    {1: 5, 2: 3, 3: 4, 4: -5, 5: -7},
    {1: 6, 2: 4, 3: -5, 4: -5},
]


def test_exact_simple_pair():
    assert exact_settlement({1: 5000, 2: -5000}) == [(2, 1, 5000)]


def test_exact_beats_greedy_on_the_known_case():
    balances = {1: 5, 2: 3, 3: 4, 4: -5, 5: -7}
    payments = exact_settlement(balances)
    assert len(payments) == 3          # greedy needs 4
    assert all(v == 0 for v in apply(balances, payments).values())


def test_exact_empty_and_settled():
    assert exact_settlement({}) == []
    assert exact_settlement({1: 0, 2: 0}) == []


def test_exact_unbalanced_is_rejected():
    with pytest.raises(ValidationError, match="add up to zero"):
        exact_settlement({1: 100, 2: -50})


@pytest.mark.parametrize("balances", CASES)
def test_exact_everyone_ends_at_zero(balances):
    payments = exact_settlement(balances)
    assert all(v == 0 for v in apply(balances, payments).values())
    assert all(amount > 0 for _, _, amount in payments)


@pytest.mark.parametrize("balances", CASES)
def test_exact_is_never_worse_than_greedy(balances):
    assert len(exact_settlement(balances)) <= len(greedy_settlement(balances))


def test_settle_uses_exact_for_small_groups():
    assert len(settle({1: 5, 2: 3, 3: 4, 4: -5, 5: -7})) == 3


def test_settle_falls_back_to_greedy_above_the_limit():
    assert len(settle({1: 5, 2: 3, 3: 4, 4: -5, 5: -7}, exact_limit=3)) == 4


import pytest

from logic.validators import ValidationError
from services import expense_service as es
from services import group_service as gs
from services import settlement_service as ss


@pytest.fixture
def setup(conn):
    g = gs.create_group(conn, "Trip")
    a, b, c = (gs.add_member(conn, g.id, n).id for n in "ABC")
    es.add_expense(conn, g.id, "Dinner", "Food", "2025-01-01",
                   payers={a: 120000}, split_method="equal",
                   total=120000, member_ids=[a, b, c])
    return g, a, b, c


def test_generate_plan_creates_pending_payments(conn, setup):
    g, a, b, c = setup
    plan = ss.generate_plan(conn, g.id)
    assert len(plan) == 2
    assert all(s.status == "Pending" and s.to_member_id == a for s in plan)
    assert sorted(s.amount for s in plan) == [40000, 40000]


def test_regenerating_does_not_duplicate(conn, setup):
    g, *_ = setup
    ss.generate_plan(conn, g.id)
    ss.generate_plan(conn, g.id)
    assert len(ss.list_settlements(conn, g.id)) == 2


def test_completed_payment_changes_the_next_plan(conn, setup):
    g, a, b, c = setup
    plan = ss.generate_plan(conn, g.id)
    ss.mark_completed(conn, plan[0].id)
    new_plan = ss.generate_plan(conn, g.id)
    assert len(new_plan) == 1
    assert len(ss.list_settlements(conn, g.id)) == 2  # 1 completed + 1 pending


def test_everything_completed_means_empty_plan(conn, setup):
    g, *_ = setup
    for s in ss.generate_plan(conn, g.id):
        ss.mark_completed(conn, s.id)
    assert ss.generate_plan(conn, g.id) == []


def test_reopen_returns_to_pending(conn, setup):
    g, *_ = setup
    s = ss.generate_plan(conn, g.id)[0]
    ss.mark_completed(conn, s.id)
    assert ss.reopen(conn, s.id).status == "Pending"


def test_history_records_events(conn, setup):
    g, *_ = setup
    plan = ss.generate_plan(conn, g.id)
    ss.mark_completed(conn, plan[0].id)
    events = [h["event"] for h in ss.history(conn, g.id)]
    assert events.count("Generated") == 2
    assert events.count("Completed") == 1


def test_missing_settlement_raises(conn):
    with pytest.raises(ValidationError):
        ss.mark_completed(conn, 9999)