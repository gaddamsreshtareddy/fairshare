"""Application layer: group and member operations.

This file sits between the UI and the lower layers. It validates input,
applies business rules, calls the repository, and turns problems into
ValidationError messages that are safe to show the user.
"""

import sqlite3
from dataclasses import dataclass

from data import repositories as repo
from data.models import Group, Member
from logic.validators import (
    ValidationError,
    validate_currency,
    validate_group_name,
    validate_member_name,
)


@dataclass
class GroupSummary:
    """Numbers shown on the group summary card."""
    group: Group
    active_member_count: int
    inactive_member_count: int
    currency_locked: bool  # True once the group has at least one expense


# ---------------------------------------------------------------------------
# Small internal helpers
# ---------------------------------------------------------------------------
def _get_member(conn, member_id: int) -> Member:
    member = repo.get_member(conn, member_id)
    if member is None:
        raise ValidationError("That member no longer exists.")
    return member


# ---------------------------------------------------------------------------
# Groups
# ---------------------------------------------------------------------------
def create_group(conn, name, base_currency="INR") -> Group:
    """Validate and create a new group."""
    clean_name = validate_group_name(name)
    clean_currency = validate_currency(base_currency)
    return repo.create_group(conn, clean_name, clean_currency)


def get_group(conn, group_id: int) -> Group:
    """Return a group, or raise ValidationError if it does not exist."""
    group = repo.get_group(conn, group_id)
    if group is None:
        raise ValidationError("That group no longer exists.")
    return group


def list_groups(conn) -> list[Group]:
    """All groups, newest first."""
    return repo.list_groups(conn)


def update_group(conn, group_id: int, name, base_currency) -> Group:
    """Rename a group and/or change its base currency.

    The currency cannot change once the group has any expense, because every
    stored amount is in the base currency and would silently change meaning.
    """
    group = get_group(conn, group_id)
    clean_name = validate_group_name(name)
    clean_currency = validate_currency(base_currency)

    if clean_currency != group.base_currency and repo.group_has_expenses(conn, group_id):
        raise ValidationError(
            "The base currency can't be changed because this group already "
            "has expenses."
        )
    return repo.update_group(conn, group_id, clean_name, clean_currency)


def get_group_summary(conn, group_id: int) -> GroupSummary:
    """Collect the numbers for the group summary card."""
    group = get_group(conn, group_id)
    members = repo.list_members(conn, group_id)
    active = sum(1 for m in members if m.is_active)
    return GroupSummary(
        group=group,
        active_member_count=active,
        inactive_member_count=len(members) - active,
        currency_locked=repo.group_has_expenses(conn, group_id),
    )


# ---------------------------------------------------------------------------
# Members
# ---------------------------------------------------------------------------
def list_members(conn, group_id: int, active_only: bool = False) -> list[Member]:
    """A group's members, sorted by name."""
    return repo.list_members(conn, group_id, active_only=active_only)


def add_member(conn, group_id: int, name) -> Member:
    """Add a member to a group.

    If a deactivated member already has this name, they are reactivated
    instead (the database does not allow two members with the same name).
    """
    clean_name = validate_member_name(name)
    get_group(conn, group_id)  # raises if the group does not exist

    existing = repo.get_member_by_name(conn, group_id, clean_name)
    if existing is not None:
        if existing.is_active:
            raise ValidationError(f"'{existing.name}' is already in this group.")
        return repo.set_member_active(conn, existing.id, True)

    try:
        return repo.add_member(conn, group_id, clean_name)
    except sqlite3.IntegrityError:
        # Safety net: the database's UNIQUE rule caught something we missed.
        raise ValidationError(f"'{clean_name}' is already in this group.") from None


def rename_member(conn, member_id: int, new_name) -> Member:
    """Rename a member. Names must stay unique within the group."""
    member = _get_member(conn, member_id)
    clean_name = validate_member_name(new_name)

    clash = repo.get_member_by_name(conn, member.group_id, clean_name)
    if clash is not None and clash.id != member.id:
        raise ValidationError(f"'{clash.name}' is already in this group.")

    try:
        return repo.rename_member(conn, member_id, clean_name)
    except sqlite3.IntegrityError:
        raise ValidationError(f"'{clean_name}' is already in this group.") from None


def deactivate_member(conn, member_id: int) -> Member:
    """Hide a member from new expenses. Their history is kept."""
    _get_member(conn, member_id)
    return repo.set_member_active(conn, member_id, False)


def reactivate_member(conn, member_id: int) -> Member:
    """Bring a deactivated member back."""
    _get_member(conn, member_id)
    return repo.set_member_active(conn, member_id, True)


def remove_member(conn, member_id: int) -> str:
    """Smart remove. Returns 'deleted' or 'deactivated'.

    A member who has never appeared in any expense, payment or settlement is
    deleted. Anyone else is only deactivated, so history and balances stay
    correct.
    """
    _get_member(conn, member_id)
    if repo.member_has_activity(conn, member_id):
        repo.set_member_active(conn, member_id, False)
        return "deactivated"
    repo.delete_member(conn, member_id)
    return "deleted"