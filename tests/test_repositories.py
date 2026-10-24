"""Tests for the data access layer (data/repositories.py).

The `conn` fixture comes from conftest.py and is a fresh temporary database.
"""

import sqlite3

import pytest

from data import repositories as repo


# ---------------------------------------------------------------------------
# Groups
# ---------------------------------------------------------------------------
def test_create_group_returns_saved_group(conn):
    group = repo.create_group(conn, "Goa Trip", "USD")
    assert group.id is not None
    assert group.name == "Goa Trip"
    assert group.base_currency == "USD"
    assert group.created_at is not None


def test_get_group_returns_the_same_group(conn):
    created = repo.create_group(conn, "Goa Trip")
    assert repo.get_group(conn, created.id) == created


def test_get_group_returns_none_when_missing(conn):
    assert repo.get_group(conn, 9999) is None


def test_list_groups_is_empty_at_first(conn):
    assert repo.list_groups(conn) == []


def test_list_groups_returns_newest_first(conn):
    repo.create_group(conn, "First")
    repo.create_group(conn, "Second")
    assert [g.name for g in repo.list_groups(conn)] == ["Second", "First"]


def test_database_still_rejects_bad_currency_code(conn):
    # The repository doesn't validate, so the Module 1 CHECK rule catches this.
    with pytest.raises(sqlite3.IntegrityError):
        repo.create_group(conn, "Bad", "RUPEES")


# ---------------------------------------------------------------------------
# Group update and currency-lock check
# ---------------------------------------------------------------------------
def insert_expense(conn, group_id):
    """Helper: insert a minimal expense directly with SQL."""
    conn.execute(
        """INSERT INTO expenses
           (group_id, title, expense_date, currency,
            original_amount, base_amount, split_method)
           VALUES (?, 'Dinner', '2025-01-01', 'INR', 100000, 100000, 'equal')""",
        (group_id,),
    )
    conn.commit()


def test_update_group_changes_name_and_currency(conn):
    group = repo.create_group(conn, "Goa Trip", "INR")
    updated = repo.update_group(conn, group.id, "Goa Trip 2025", "USD")
    assert updated.name == "Goa Trip 2025"
    assert updated.base_currency == "USD"
    assert updated.id == group.id                  # same group
    assert updated.created_at == group.created_at  # creation time untouched


def test_update_group_returns_none_when_missing(conn):
    assert repo.update_group(conn, 9999, "Ghost", "INR") is None


def test_update_group_with_blank_name_is_rejected_and_changes_nothing(conn):
    group = repo.create_group(conn, "Goa Trip")
    with pytest.raises(sqlite3.IntegrityError):
        repo.update_group(conn, group.id, "   ", "INR")
    assert repo.get_group(conn, group.id).name == "Goa Trip"


def test_new_group_has_no_expenses(conn):
    group = repo.create_group(conn, "Goa Trip")
    assert repo.group_has_expenses(conn, group.id) is False


def test_group_with_an_expense_reports_true(conn):
    group = repo.create_group(conn, "Goa Trip")
    insert_expense(conn, group.id)
    assert repo.group_has_expenses(conn, group.id) is True


def test_expense_in_another_group_does_not_count(conn):
    trip = repo.create_group(conn, "Trip")
    flat = repo.create_group(conn, "Flat")
    insert_expense(conn, trip.id)
    assert repo.group_has_expenses(conn, trip.id) is True
    assert repo.group_has_expenses(conn, flat.id) is False


# ---------------------------------------------------------------------------
# Members
# ---------------------------------------------------------------------------
def new_expense_id(conn, group_id):
    """Helper: insert a minimal expense and return its id."""
    cur = conn.execute(
        """INSERT INTO expenses
           (group_id, title, expense_date, currency,
            original_amount, base_amount, split_method)
           VALUES (?, 'Dinner', '2025-01-01', 'INR', 100000, 100000, 'equal')""",
        (group_id,),
    )
    conn.commit()
    return cur.lastrowid


def test_add_member_returns_saved_member(conn):
    group = repo.create_group(conn, "Trip")
    member = repo.add_member(conn, group.id, "Ravi")
    assert member.id is not None
    assert member.name == "Ravi"
    assert member.group_id == group.id
    assert member.is_active is True


def test_add_member_rejects_duplicate_name(conn):
    group = repo.create_group(conn, "Trip")
    repo.add_member(conn, group.id, "Ravi")
    with pytest.raises(sqlite3.IntegrityError):
        repo.add_member(conn, group.id, "Ravi")


def test_add_member_duplicate_check_ignores_case(conn):
    group = repo.create_group(conn, "Trip")
    repo.add_member(conn, group.id, "Ravi")
    with pytest.raises(sqlite3.IntegrityError):
        repo.add_member(conn, group.id, "RAVI")


def test_get_member_returns_the_member(conn):
    group = repo.create_group(conn, "Trip")
    created = repo.add_member(conn, group.id, "Ravi")
    assert repo.get_member(conn, created.id) == created


def test_get_member_returns_none_when_missing(conn):
    assert repo.get_member(conn, 9999) is None


def test_get_member_by_name_ignores_case(conn):
    group = repo.create_group(conn, "Trip")
    created = repo.add_member(conn, group.id, "Ravi")
    assert repo.get_member_by_name(conn, group.id, "ravi") == created
    assert repo.get_member_by_name(conn, group.id, "Nobody") is None


def test_get_member_by_name_only_searches_one_group(conn):
    trip = repo.create_group(conn, "Trip")
    flat = repo.create_group(conn, "Flat")
    repo.add_member(conn, trip.id, "Ravi")
    assert repo.get_member_by_name(conn, flat.id, "Ravi") is None


def test_list_members_empty_at_first(conn):
    group = repo.create_group(conn, "Trip")
    assert repo.list_members(conn, group.id) == []


def test_list_members_sorted_by_name_ignoring_case(conn):
    group = repo.create_group(conn, "Trip")
    for name in ["Ravi", "anita", "Bala"]:
        repo.add_member(conn, group.id, name)
    names = [m.name for m in repo.list_members(conn, group.id)]
    assert names == ["anita", "Bala", "Ravi"]


def test_list_members_only_returns_that_groups_members(conn):
    trip = repo.create_group(conn, "Trip")
    flat = repo.create_group(conn, "Flat")
    repo.add_member(conn, trip.id, "Ravi")
    repo.add_member(conn, flat.id, "Anita")
    assert [m.name for m in repo.list_members(conn, trip.id)] == ["Ravi"]


def test_list_members_active_only(conn):
    group = repo.create_group(conn, "Trip")
    ravi = repo.add_member(conn, group.id, "Ravi")
    repo.add_member(conn, group.id, "Anita")
    repo.set_member_active(conn, ravi.id, False)
    assert len(repo.list_members(conn, group.id)) == 2
    active = repo.list_members(conn, group.id, active_only=True)
    assert [m.name for m in active] == ["Anita"]


def test_rename_member_changes_name(conn):
    group = repo.create_group(conn, "Trip")
    member = repo.add_member(conn, group.id, "Ravi")
    renamed = repo.rename_member(conn, member.id, "Ravi Kumar")
    assert renamed.name == "Ravi Kumar"
    assert renamed.id == member.id


def test_rename_member_returns_none_when_missing(conn):
    assert repo.rename_member(conn, 9999, "Ghost") is None


def test_rename_to_existing_name_is_rejected_and_changes_nothing(conn):
    group = repo.create_group(conn, "Trip")
    repo.add_member(conn, group.id, "Anita")
    ravi = repo.add_member(conn, group.id, "Ravi")
    with pytest.raises(sqlite3.IntegrityError):
        repo.rename_member(conn, ravi.id, "anita")
    assert repo.get_member(conn, ravi.id).name == "Ravi"


def test_rename_can_change_capitalization_of_own_name(conn):
    group = repo.create_group(conn, "Trip")
    member = repo.add_member(conn, group.id, "ravi")
    assert repo.rename_member(conn, member.id, "Ravi").name == "Ravi"


def test_deactivate_and_reactivate_member(conn):
    group = repo.create_group(conn, "Trip")
    member = repo.add_member(conn, group.id, "Ravi")
    assert repo.set_member_active(conn, member.id, False).is_active is False
    assert repo.set_member_active(conn, member.id, True).is_active is True


def test_set_member_active_returns_none_when_missing(conn):
    assert repo.set_member_active(conn, 9999, False) is None


def test_new_member_has_no_activity(conn):
    group = repo.create_group(conn, "Trip")
    member = repo.add_member(conn, group.id, "Ravi")
    assert repo.member_has_activity(conn, member.id) is False


def test_payer_counts_as_activity(conn):
    group = repo.create_group(conn, "Trip")
    member = repo.add_member(conn, group.id, "Ravi")
    expense_id = new_expense_id(conn, group.id)
    conn.execute(
        "INSERT INTO expense_payers (expense_id, member_id, amount_paid) "
        "VALUES (?, ?, 100000)",
        (expense_id, member.id),
    )
    conn.commit()
    assert repo.member_has_activity(conn, member.id) is True


def test_split_counts_as_activity(conn):
    group = repo.create_group(conn, "Trip")
    member = repo.add_member(conn, group.id, "Ravi")
    expense_id = new_expense_id(conn, group.id)
    conn.execute(
        "INSERT INTO expense_splits (expense_id, member_id, share_amount) "
        "VALUES (?, ?, 100000)",
        (expense_id, member.id),
    )
    conn.commit()
    assert repo.member_has_activity(conn, member.id) is True


def test_item_consumer_counts_as_activity(conn):
    group = repo.create_group(conn, "Trip")
    member = repo.add_member(conn, group.id, "Ravi")
    expense_id = new_expense_id(conn, group.id)
    cur = conn.execute(
        "INSERT INTO items (expense_id, name, amount) VALUES (?, 'Pizza', 50000)",
        (expense_id,),
    )
    conn.execute(
        "INSERT INTO item_consumers (item_id, member_id) VALUES (?, ?)",
        (cur.lastrowid, member.id),
    )
    conn.commit()
    assert repo.member_has_activity(conn, member.id) is True


def test_settlement_receiver_counts_as_activity(conn):
    group = repo.create_group(conn, "Trip")
    payer = repo.add_member(conn, group.id, "Ravi")
    receiver = repo.add_member(conn, group.id, "Anita")
    conn.execute(
        "INSERT INTO settlements (group_id, from_member_id, to_member_id, amount) "
        "VALUES (?, ?, ?, 5000)",
        (group.id, payer.id, receiver.id),
    )
    conn.commit()
    assert repo.member_has_activity(conn, payer.id) is True
    assert repo.member_has_activity(conn, receiver.id) is True


def test_delete_member_removes_unused_member(conn):
    group = repo.create_group(conn, "Trip")
    member = repo.add_member(conn, group.id, "Ravi")
    assert repo.delete_member(conn, member.id) is True
    assert repo.get_member(conn, member.id) is None


def test_delete_member_returns_false_when_missing(conn):
    assert repo.delete_member(conn, 9999) is False


def test_delete_member_with_activity_is_refused(conn):
    group = repo.create_group(conn, "Trip")
    member = repo.add_member(conn, group.id, "Ravi")
    expense_id = new_expense_id(conn, group.id)
    conn.execute(
        "INSERT INTO expense_payers (expense_id, member_id, amount_paid) "
        "VALUES (?, ?, 100000)",
        (expense_id, member.id),
    )
    conn.commit()
    with pytest.raises(sqlite3.IntegrityError):
        repo.delete_member(conn, member.id)
    assert repo.get_member(conn, member.id) is not None  # still there