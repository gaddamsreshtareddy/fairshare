"""Data access layer: every SQL statement for FairShare lives in this file.

Rules for this file:
- Every function takes an open database connection `conn` as its first argument.
- Functions save and fetch data. They do not decide what is valid;
  that is the job of the logic and service layers above.
- Functions return model objects (Group, Member, ...), never raw rows.
"""

from data.models import Group, Member


# ---------------------------------------------------------------------------
# Groups
# ---------------------------------------------------------------------------
def create_group(conn, name: str, base_currency: str = "INR") -> Group:
    """Insert a new group and return it (with its new id)."""
    cur = conn.execute(
        "INSERT INTO groups (name, base_currency) VALUES (?, ?)",
        (name, base_currency),
    )
    conn.commit()
    return get_group(conn, cur.lastrowid)


def get_group(conn, group_id: int) -> Group | None:
    """Return one group, or None if no group has that id."""
    row = conn.execute("SELECT * FROM groups WHERE id = ?", (group_id,)).fetchone()
    return Group.from_row(row) if row else None


def list_groups(conn) -> list[Group]:
    """Return all groups, newest first."""
    rows = conn.execute("SELECT * FROM groups ORDER BY created_at DESC, id DESC")
    return [Group.from_row(row) for row in rows]


def update_group(conn, group_id: int, name: str, base_currency: str) -> Group | None:
    """Change a group's name and base currency.

    Returns the updated group, or None if no group has that id.
    (Whether the currency is *allowed* to change is decided in the service layer.)
    """
    cur = conn.execute(
        "UPDATE groups SET name = ?, base_currency = ? WHERE id = ?",
        (name, base_currency, group_id),
    )
    conn.commit()
    return get_group(conn, group_id) if cur.rowcount else None


def group_has_expenses(conn, group_id: int) -> bool:
    """True if the group has at least one expense (used for the currency lock)."""
    row = conn.execute(
        "SELECT 1 FROM expenses WHERE group_id = ? LIMIT 1", (group_id,)
    ).fetchone()
    return row is not None


# ---------------------------------------------------------------------------
# Members
# ---------------------------------------------------------------------------
def add_member(conn, group_id: int, name: str) -> Member:
    """Insert a new member and return it (with its new id)."""
    cur = conn.execute(
        "INSERT INTO members (group_id, name) VALUES (?, ?)", (group_id, name)
    )
    conn.commit()
    return get_member(conn, cur.lastrowid)


def get_member(conn, member_id: int) -> Member | None:
    """Return one member, or None if no member has that id."""
    row = conn.execute("SELECT * FROM members WHERE id = ?", (member_id,)).fetchone()
    return Member.from_row(row) if row else None


def get_member_by_name(conn, group_id: int, name: str) -> Member | None:
    """Find a member by name inside one group. Capitalization is ignored."""
    row = conn.execute(
        "SELECT * FROM members WHERE group_id = ? AND name = ?", (group_id, name)
    ).fetchone()
    return Member.from_row(row) if row else None


def list_members(conn, group_id: int, active_only: bool = False) -> list[Member]:
    """Return a group's members sorted by name. Optionally only active ones."""
    sql = "SELECT * FROM members WHERE group_id = ?"
    if active_only:
        sql += " AND is_active = 1"
    sql += " ORDER BY name COLLATE NOCASE, id"
    return [Member.from_row(row) for row in conn.execute(sql, (group_id,))]


def rename_member(conn, member_id: int, new_name: str) -> Member | None:
    """Change a member's name. Returns None if no member has that id."""
    cur = conn.execute(
        "UPDATE members SET name = ? WHERE id = ?", (new_name, member_id)
    )
    conn.commit()
    return get_member(conn, member_id) if cur.rowcount else None


def set_member_active(conn, member_id: int, is_active: bool) -> Member | None:
    """Deactivate (False) or reactivate (True) a member."""
    cur = conn.execute(
        "UPDATE members SET is_active = ? WHERE id = ?",
        (1 if is_active else 0, member_id),
    )
    conn.commit()
    return get_member(conn, member_id) if cur.rowcount else None


def member_has_activity(conn, member_id: int) -> bool:
    """True if the member appears anywhere in expense or settlement data.

    Such a member must never be hard-deleted, only deactivated.
    """
    row = conn.execute(
        """SELECT 1 WHERE
              EXISTS (SELECT 1 FROM expense_payers WHERE member_id = :id)
           OR EXISTS (SELECT 1 FROM expense_splits WHERE member_id = :id)
           OR EXISTS (SELECT 1 FROM item_consumers WHERE member_id = :id)
           OR EXISTS (SELECT 1 FROM settlements
                      WHERE from_member_id = :id OR to_member_id = :id)
           OR EXISTS (SELECT 1 FROM settlement_history
                      WHERE from_member_id = :id OR to_member_id = :id)""",
        {"id": member_id},
    ).fetchone()
    return row is not None


def delete_member(conn, member_id: int) -> bool:
    """Hard-delete a member. Returns True if a member was deleted.

    SQLite refuses (IntegrityError) if the member appears in any expense or
    settlement. The service layer checks member_has_activity() first.
    """
    cur = conn.execute("DELETE FROM members WHERE id = ?", (member_id,))
    conn.commit()
    return cur.rowcount > 0