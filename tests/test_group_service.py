"""Tests for the group service (services/group_service.py).

The `conn` fixture comes from conftest.py and is a fresh temporary database.
"""

import pytest

from data import repositories as repo
from logic.validators import ValidationError
from services import group_service as svc


def insert_expense(conn, group_id):
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


def make_member_pay(conn, group_id, member_id):
    """Helper: give a member 'activity' by making them pay for an expense."""
    expense_id = insert_expense(conn, group_id)
    conn.execute(
        "INSERT INTO expense_payers (expense_id, member_id, amount_paid) "
        "VALUES (?, ?, 100000)",
        (expense_id, member_id),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Groups
# ---------------------------------------------------------------------------
def test_create_group_cleans_name_and_currency(conn):
    group = svc.create_group(conn, "  Goa   Trip ", "usd")
    assert group.name == "Goa Trip"
    assert group.base_currency == "USD"


def test_create_group_defaults_to_inr(conn):
    assert svc.create_group(conn, "Flat").base_currency == "INR"


def test_create_group_blank_name_is_rejected(conn):
    with pytest.raises(ValidationError, match="Group name is required"):
        svc.create_group(conn, "   ")


def test_create_group_unsupported_currency_is_rejected(conn):
    with pytest.raises(ValidationError, match="not supported"):
        svc.create_group(conn, "Trip", "JPY")


def test_invalid_group_is_not_saved(conn):
    with pytest.raises(ValidationError):
        svc.create_group(conn, "")
    assert svc.list_groups(conn) == []


def test_get_group_returns_the_group(conn):
    created = svc.create_group(conn, "Trip")
    assert svc.get_group(conn, created.id) == created


def test_get_group_missing_raises(conn):
    with pytest.raises(ValidationError, match="no longer exists"):
        svc.get_group(conn, 9999)


def test_list_groups_returns_all_groups(conn):
    svc.create_group(conn, "Trip")
    svc.create_group(conn, "Flat")
    assert {g.name for g in svc.list_groups(conn)} == {"Trip", "Flat"}


def test_update_group_changes_name(conn):
    group = svc.create_group(conn, "Trip")
    updated = svc.update_group(conn, group.id, "  Goa  Trip ", "INR")
    assert updated.name == "Goa Trip"


def test_update_group_can_change_currency_before_any_expense(conn):
    group = svc.create_group(conn, "Trip", "INR")
    assert svc.update_group(conn, group.id, "Trip", "eur").base_currency == "EUR"


def test_currency_is_locked_once_group_has_an_expense(conn):
    group = svc.create_group(conn, "Trip", "INR")
    insert_expense(conn, group.id)
    with pytest.raises(ValidationError, match="can't be changed"):
        svc.update_group(conn, group.id, "Trip", "USD")
    assert repo.get_group(conn, group.id).base_currency == "INR"  # unchanged


def test_name_can_still_change_when_currency_is_locked(conn):
    group = svc.create_group(conn, "Trip", "INR")
    insert_expense(conn, group.id)
    updated = svc.update_group(conn, group.id, "Goa Trip", "INR")  # same currency
    assert updated.name == "Goa Trip"


def test_update_missing_group_raises(conn):
    with pytest.raises(ValidationError, match="no longer exists"):
        svc.update_group(conn, 9999, "Ghost", "INR")


def test_update_group_with_blank_name_keeps_old_name(conn):
    group = svc.create_group(conn, "Trip")
    with pytest.raises(ValidationError):
        svc.update_group(conn, group.id, "  ", "INR")
    assert repo.get_group(conn, group.id).name == "Trip"


# ---------------------------------------------------------------------------
# Members: add
# ---------------------------------------------------------------------------
def test_add_member_cleans_name(conn):
    group = svc.create_group(conn, "Trip")
    member = svc.add_member(conn, group.id, "  Ravi   Kumar ")
    assert member.name == "Ravi Kumar"
    assert member.is_active is True


def test_add_member_blank_name_is_rejected(conn):
    group = svc.create_group(conn, "Trip")
    with pytest.raises(ValidationError, match="Member name is required"):
        svc.add_member(conn, group.id, "  ")


def test_add_member_to_missing_group_raises(conn):
    with pytest.raises(ValidationError, match="no longer exists"):
        svc.add_member(conn, 9999, "Ravi")


def test_add_duplicate_member_is_rejected_ignoring_case(conn):
    group = svc.create_group(conn, "Trip")
    svc.add_member(conn, group.id, "Ravi")
    with pytest.raises(ValidationError, match="already in this group"):
        svc.add_member(conn, group.id, "  rAVI ")
    assert len(svc.list_members(conn, group.id)) == 1


def test_adding_a_deactivated_member_reactivates_them(conn):
    group = svc.create_group(conn, "Trip")
    ravi = svc.add_member(conn, group.id, "Ravi")
    svc.deactivate_member(conn, ravi.id)
    again = svc.add_member(conn, group.id, "ravi")
    assert again.id == ravi.id          # same person, not a new row
    assert again.is_active is True
    assert len(svc.list_members(conn, group.id)) == 1


# ---------------------------------------------------------------------------
# Members: rename
# ---------------------------------------------------------------------------
def test_rename_member(conn):
    group = svc.create_group(conn, "Trip")
    ravi = svc.add_member(conn, group.id, "Ravi")
    assert svc.rename_member(conn, ravi.id, " Ravi  Kumar ").name == "Ravi Kumar"


def test_rename_to_another_members_name_is_rejected(conn):
    group = svc.create_group(conn, "Trip")
    svc.add_member(conn, group.id, "Anita")
    ravi = svc.add_member(conn, group.id, "Ravi")
    with pytest.raises(ValidationError, match="already in this group"):
        svc.rename_member(conn, ravi.id, "ANITA")
    assert repo.get_member(conn, ravi.id).name == "Ravi"


def test_rename_can_change_only_capitalization(conn):
    group = svc.create_group(conn, "Trip")
    ravi = svc.add_member(conn, group.id, "ravi")
    assert svc.rename_member(conn, ravi.id, "Ravi").name == "Ravi"


def test_rename_missing_member_raises(conn):
    with pytest.raises(ValidationError, match="no longer exists"):
        svc.rename_member(conn, 9999, "Ghost")


# ---------------------------------------------------------------------------
# Members: deactivate, reactivate, remove
# ---------------------------------------------------------------------------
def test_deactivate_member(conn):
    group = svc.create_group(conn, "Trip")
    ravi = svc.add_member(conn, group.id, "Ravi")
    assert svc.deactivate_member(conn, ravi.id).is_active is False


def test_reactivate_member(conn):
    group = svc.create_group(conn, "Trip")
    ravi = svc.add_member(conn, group.id, "Ravi")
    svc.deactivate_member(conn, ravi.id)
    assert svc.reactivate_member(conn, ravi.id).is_active is True


def test_deactivate_missing_member_raises(conn):
    with pytest.raises(ValidationError, match="no longer exists"):
        svc.deactivate_member(conn, 9999)


def test_remove_unused_member_deletes_them(conn):
    group = svc.create_group(conn, "Trip")
    ravi = svc.add_member(conn, group.id, "Ravi")
    assert svc.remove_member(conn, ravi.id) == "deleted"
    assert repo.get_member(conn, ravi.id) is None


def test_remove_member_with_activity_only_deactivates(conn):
    group = svc.create_group(conn, "Trip")
    ravi = svc.add_member(conn, group.id, "Ravi")
    make_member_pay(conn, group.id, ravi.id)
    assert svc.remove_member(conn, ravi.id) == "deactivated"
    kept = repo.get_member(conn, ravi.id)
    assert kept is not None             # history is preserved
    assert kept.is_active is False


def test_remove_missing_member_raises(conn):
    with pytest.raises(ValidationError, match="no longer exists"):
        svc.remove_member(conn, 9999)


def test_list_members_active_only(conn):
    group = svc.create_group(conn, "Trip")
    ravi = svc.add_member(conn, group.id, "Ravi")
    svc.add_member(conn, group.id, "Anita")
    svc.deactivate_member(conn, ravi.id)
    assert [m.name for m in svc.list_members(conn, group.id, active_only=True)] == ["Anita"]
    assert len(svc.list_members(conn, group.id)) == 2


# ---------------------------------------------------------------------------
# Group summary
# ---------------------------------------------------------------------------
def test_group_summary_counts_members(conn):
    group = svc.create_group(conn, "Trip", "USD")
    ravi = svc.add_member(conn, group.id, "Ravi")
    svc.add_member(conn, group.id, "Anita")
    svc.add_member(conn, group.id, "Bala")
    svc.deactivate_member(conn, ravi.id)
    summary = svc.get_group_summary(conn, group.id)
    assert summary.group.base_currency == "USD"
    assert summary.active_member_count == 2
    assert summary.inactive_member_count == 1
    assert summary.currency_locked is False


def test_group_summary_shows_currency_lock_after_an_expense(conn):
    group = svc.create_group(conn, "Trip")
    insert_expense(conn, group.id)
    assert svc.get_group_summary(conn, group.id).currency_locked is True