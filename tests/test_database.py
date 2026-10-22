"""Tests for the database layer (data/database.py).

Every test uses a temporary database file, never the real one.
"""

import pytest
import sqlite3

from data.database import get_connection, init_db
from data.models import Group, Member

EXPECTED_TABLES = {
    "groups", "members", "expenses", "expense_payers", "expense_splits",
    "items", "item_consumers", "settlements", "settlement_history",
}


@pytest.fixture
def conn(tmp_path):
    """A fresh, empty FairShare database for one test.

    tmp_path is a temporary folder that pytest creates and cleans up.
    Code before 'yield' is setup; code after it is cleanup.
    """
    db_file = tmp_path / "test.db"
    init_db(db_file)
    connection = get_connection(db_file)
    yield connection
    connection.close()


def table_names(connection):
    rows = connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    return {row["name"] for row in rows}


def test_all_tables_are_created(conn):
    assert EXPECTED_TABLES.issubset(table_names(conn))


def test_init_db_can_run_twice(tmp_path):
    db_file = tmp_path / "twice.db"
    init_db(db_file)
    init_db(db_file)  # second call must not fail or erase anything
    connection = get_connection(db_file)
    try:
        assert EXPECTED_TABLES.issubset(table_names(connection))
    finally:
        connection.close()


def test_foreign_keys_are_enabled(conn):
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1


# ---------------------------------------------------------------------------
# Group and member tests
# ---------------------------------------------------------------------------
def add_group(connection, name="Goa Trip", currency="INR"):
    """Helper: insert a group and return its new id."""
    cur = connection.execute(
        "INSERT INTO groups (name, base_currency) VALUES (?, ?)", (name, currency)
    )
    connection.commit()
    return cur.lastrowid


def add_member(connection, group_id, name):
    """Helper: insert a member and return its new id."""
    cur = connection.execute(
        "INSERT INTO members (group_id, name) VALUES (?, ?)", (group_id, name)
    )
    connection.commit()
    return cur.lastrowid


def test_group_can_be_saved_and_read_back(conn):
    group_id = add_group(conn, "Goa Trip", "USD")
    row = conn.execute("SELECT * FROM groups WHERE id = ?", (group_id,)).fetchone()
    group = Group.from_row(row)
    assert group.id == group_id
    assert group.name == "Goa Trip"
    assert group.base_currency == "USD"
    assert group.created_at is not None  # the database filled in the timestamp


def test_group_currency_defaults_to_inr(conn):
    cur = conn.execute("INSERT INTO groups (name) VALUES ('Roommates')")
    row = conn.execute("SELECT * FROM groups WHERE id = ?", (cur.lastrowid,)).fetchone()
    assert Group.from_row(row).base_currency == "INR"


def test_blank_group_name_is_rejected(conn):
    with pytest.raises(sqlite3.IntegrityError):
        add_group(conn, "   ")


def test_member_can_be_saved_and_read_back(conn):
    group_id = add_group(conn)
    member_id = add_member(conn, group_id, "Ravi")
    row = conn.execute("SELECT * FROM members WHERE id = ?", (member_id,)).fetchone()
    member = Member.from_row(row)
    assert member.name == "Ravi"
    assert member.group_id == group_id
    assert member.is_active is True  # new members start active


def test_duplicate_member_name_in_same_group_is_rejected(conn):
    group_id = add_group(conn)
    add_member(conn, group_id, "Ravi")
    with pytest.raises(sqlite3.IntegrityError):
        add_member(conn, group_id, "Ravi")


def test_duplicate_check_ignores_capitalization(conn):
    group_id = add_group(conn)
    add_member(conn, group_id, "Ravi")
    with pytest.raises(sqlite3.IntegrityError):
        add_member(conn, group_id, "ravi")


def test_same_name_is_allowed_in_different_groups(conn):
    group_a = add_group(conn, "Trip")
    group_b = add_group(conn, "Flat")
    add_member(conn, group_a, "Ravi")
    add_member(conn, group_b, "Ravi")  # must NOT raise


def test_blank_member_name_is_rejected(conn):
    group_id = add_group(conn)
    with pytest.raises(sqlite3.IntegrityError):
        add_member(conn, group_id, "  ")


# ---------------------------------------------------------------------------
# Constraint tests: the database must refuse bad data
# ---------------------------------------------------------------------------
def add_expense(connection, group_id, amount=100000, category="Food",
                split_method="equal"):
    """Helper: insert an expense and return its new id."""
    cur = connection.execute(
        """INSERT INTO expenses
           (group_id, title, category, expense_date, currency,
            original_amount, base_amount, split_method)
           VALUES (?, 'Dinner', ?, '2025-01-01', 'INR', ?, ?, ?)""",
        (group_id, category, amount, amount, split_method),
    )
    connection.commit()
    return cur.lastrowid


@pytest.mark.parametrize("bad_amount", [0, -500])
def test_expense_amount_must_be_positive(conn, bad_amount):
    group_id = add_group(conn)
    with pytest.raises(sqlite3.IntegrityError):
        add_expense(conn, group_id, amount=bad_amount)


@pytest.mark.parametrize("bad_amount", [0, -500])
def test_payer_amount_must_be_positive(conn, bad_amount):
    group_id = add_group(conn)
    member_id = add_member(conn, group_id, "Ravi")
    expense_id = add_expense(conn, group_id)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO expense_payers (expense_id, member_id, amount_paid) "
            "VALUES (?, ?, ?)",
            (expense_id, member_id, bad_amount),
        )


def test_split_share_cannot_be_negative(conn):
    group_id = add_group(conn)
    member_id = add_member(conn, group_id, "Ravi")
    expense_id = add_expense(conn, group_id)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO expense_splits (expense_id, member_id, share_amount) "
            "VALUES (?, ?, -1)",
            (expense_id, member_id),
        )


def test_percentage_cannot_exceed_100(conn):
    group_id = add_group(conn)
    member_id = add_member(conn, group_id, "Ravi")
    expense_id = add_expense(conn, group_id)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO expense_splits (expense_id, member_id, share_amount, percentage) "
            "VALUES (?, ?, 1000, 150)",
            (expense_id, member_id),
        )


def test_unknown_category_is_rejected(conn):
    group_id = add_group(conn)
    with pytest.raises(sqlite3.IntegrityError):
        add_expense(conn, group_id, category="Gambling")


def test_unknown_split_method_is_rejected(conn):
    group_id = add_group(conn)
    with pytest.raises(sqlite3.IntegrityError):
        add_expense(conn, group_id, split_method="random")


def test_expense_for_nonexistent_group_is_rejected(conn):
    with pytest.raises(sqlite3.IntegrityError):
        add_expense(conn, group_id=9999)


def test_payer_must_be_a_real_member(conn):
    group_id = add_group(conn)
    expense_id = add_expense(conn, group_id)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO expense_payers (expense_id, member_id, amount_paid) "
            "VALUES (?, 9999, 1000)",
            (expense_id,),
        )


def test_settlement_to_self_is_rejected(conn):
    group_id = add_group(conn)
    member_id = add_member(conn, group_id, "Ravi")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO settlements (group_id, from_member_id, to_member_id, amount) "
            "VALUES (?, ?, ?, 1000)",
            (group_id, member_id, member_id),
        )


def test_deleting_group_removes_its_members_and_expenses(conn):
    group_id = add_group(conn)
    add_member(conn, group_id, "Ravi")
    add_expense(conn, group_id)
    conn.execute("DELETE FROM groups WHERE id = ?", (group_id,))
    conn.commit()
    assert conn.execute("SELECT COUNT(*) FROM members").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM expenses").fetchone()[0] == 0


def test_member_in_an_expense_cannot_be_hard_deleted(conn):
    group_id = add_group(conn)
    member_id = add_member(conn, group_id, "Ravi")
    expense_id = add_expense(conn, group_id)
    conn.execute(
        "INSERT INTO expense_payers (expense_id, member_id, amount_paid) "
        "VALUES (?, ?, 100000)",
        (expense_id, member_id),
    )
    conn.commit()
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("DELETE FROM members WHERE id = ?", (member_id,))