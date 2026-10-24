import sqlite3

import pytest

from data import repositories as repo
from data.models import Expense, PayerShare, Split
from logic.validators import ValidationError
from services import expense_service as es
from services import group_service as gs


@pytest.fixture
def setup(conn):
    """A group with three members. Returns (group, a, b, c) ids."""
    group = gs.create_group(conn, "Trip")
    a, b, c = (
        gs.add_member(conn, group.id, n).id
        for n in ["A", "B", "C"]
    )
    return group, a, b, c

def test_equal_split_saved_and_reloaded(conn, setup):
    group, a, b, c = setup

    expense = es.add_expense(
        conn,
        group.id,
        "Dinner",
        "Food",
        "2025-01-01",
        payers={a: 120000},
        split_method="equal",
        total=120000,
        member_ids=[a, b, c],
    )

    loaded = es.get_expense(conn, expense.id)

    assert len(loaded.payers) == 1
    assert len(loaded.splits) == 3
    assert [s.share_amount for s in loaded.splits] == [40000, 40000, 40000]
    assert loaded.currency == "INR"

def test_custom_split(conn, setup):
    group, a, b, c = setup

    expense = es.add_expense(
        conn,
        group.id,
        "Hotel",
        "Hotel",
        "2025-01-02",
        payers={a: 100000},
        split_method="custom",
        total=100000,
        shares={
            a: 20000,
            b: 30000,
            c: 50000,
        },
    )

    assert [s.share_amount for s in expense.splits] == [20000, 30000, 50000]

def test_percentage_split_stores_percentages(conn, setup):
    group, a, b, c = setup

    expense = es.add_expense(
        conn,
        group.id,
        "Shopping",
        "Shopping",
        "2025-01-03",
        payers={a: 100000},
        split_method="percentage",
        total=100000,
        percentages={
            a: "20",
            b: "30",
            c: "50",
        },
    )

    assert [s.share_amount for s in expense.splits] == [20000, 30000, 50000]
    assert [s.percentage for s in expense.splits] == [20.0, 30.0, 50.0]

def test_item_split_saves_items_and_consumers(conn, setup):
    group, a, b, c = setup

    expense = es.add_expense(
        conn,
        group.id,
        "Party",
        "Food",
        "2025-01-04",
        payers={a: 70000, b: 50000},
        split_method="item",
        items=[
            ("Pizza", 60000, [a, b]),
            ("Drinks", 30000, [b, c]),
            ("Dessert", 30000, [a]),
        ],
    )

    assert expense.original_amount == 120000
    assert [s.share_amount for s in expense.splits] == [60000, 45000, 15000]
    assert len(expense.items) == 3
    assert expense.items[0].name == "Pizza"
    assert expense.items[0].consumer_ids == [a, b]

def test_two_payers(conn, setup):
    group, a, b, c = setup

    expense = es.add_expense(
        conn,
        group.id,
        "Dinner",
        "Food",
        "2025-01-05",
        payers={a: 70000, b: 50000},
        split_method="equal",
        total=120000,
        member_ids=[a, b, c],
    )

    assert len(expense.payers) == 2
    assert [(p.member_id, p.amount_paid) for p in expense.payers] == [
        (a, 70000),
        (b, 50000),
    ]

def test_blank_title_rejected(conn, setup):
    group, a, b, c = setup

    with pytest.raises(ValidationError, match="Title"):
        es.add_expense(
            conn,
            group.id,
            "   ",
            "Food",
            "2025-01-06",
            payers={a: 120000},
            split_method="equal",
            total=120000,
            member_ids=[a, b, c],
        )

def test_bad_category_rejected(conn, setup):
    group, a, b, c = setup

    with pytest.raises(ValidationError):
        es.add_expense(
            conn,
            group.id,
            "Dinner",
            "Gambling",
            "2025-01-07",
            payers={a: 120000},
            split_method="equal",
            total=120000,
            member_ids=[a, b, c],
        )

def test_bad_date_rejected(conn, setup):
    group, a, b, c = setup

    with pytest.raises(ValidationError):
        es.add_expense(
            conn,
            group.id,
            "Dinner",
            "Food",
            "2025-13-45",
            payers={a: 120000},
            split_method="equal",
            total=120000,
            member_ids=[a, b, c],
        )

def test_unknown_split_method_rejected(conn, setup):
    group, a, b, c = setup

    with pytest.raises(ValidationError):
        es.add_expense(
            conn,
            group.id,
            "Dinner",
            "Food",
            "2025-01-08",
            payers={a: 120000},
            split_method="random",
            total=120000,
            member_ids=[a, b, c],
        )

def test_payer_from_another_group_rejected(conn, setup):
    group, a, b, c = setup

    other_group = gs.create_group(conn, "Other Group")
    other_member = gs.add_member(conn, other_group.id, "Other").id

    with pytest.raises(ValidationError):
        es.add_expense(
            conn,
            group.id,
            "Dinner",
            "Food",
            "2025-01-09",
            payers={other_member: 120000},
            split_method="equal",
            total=120000,
            member_ids=[a, b, c],
        )

def test_payers_not_adding_up_saves_nothing(conn, setup):
    group, a, b, c = setup

    with pytest.raises(ValidationError):
        es.add_expense(
            conn,
            group.id,
            "Bad Dinner",
            "Food",
            "2025-01-10",
            payers={a: 100},
            split_method="equal",
            total=120000,
            member_ids=[a, b, c],
        )

    assert es.list_expenses(conn, group.id) == []

def test_list_expenses_newest_date_first(conn, setup):
    group, a, b, c = setup

    es.add_expense(
        conn,
        group.id,
        "January Dinner",
        "Food",
        "2025-01-01",
        payers={a: 60000},
        split_method="equal",
        total=60000,
        member_ids=[a, b, c],
    )

    es.add_expense(
        conn,
        group.id,
        "February Dinner",
        "Food",
        "2025-02-01",
        payers={a: 60000},
        split_method="equal",
        total=60000,
        member_ids=[a, b, c],
    )

    expenses = es.list_expenses(conn, group.id)

    assert expenses[0].title == "February Dinner"
    assert expenses[1].title == "January Dinner"

def test_get_missing_expense_raises(conn, setup):
    with pytest.raises(ValidationError):
        es.get_expense(conn, 9999)

def test_repository_rollback_leaves_nothing(conn, setup):
    group, a, b, c = setup

    expense = Expense(
        id=None,
        group_id=group.id,
        title="Broken Expense",
        expense_date="2025-01-11",
        currency="INR",
        original_amount=1000,
        base_amount=1000,
        split_method="equal",
        payers=[
            PayerShare(member_id=9999, amount_paid=1000)
        ],
        splits=[
            Split(member_id=a, share_amount=1000)
        ],
    )

    with pytest.raises(sqlite3.IntegrityError):
        repo.create_expense(conn, expense)

    assert repo.list_expenses(conn, group.id) == []

    count = conn.execute(
        "SELECT COUNT(*) FROM expense_splits"
    ).fetchone()[0]

    assert count == 0