"""Data access layer: every SQL statement for FairShare lives in this file.

Rules for this file:
- Every function takes an open database connection `conn` as its first argument.
- Functions save and fetch data. They do not decide what is valid;
  that is the job of the logic and service layers above.
- Functions return model objects (Group, Member, ...), never raw rows.
"""
from data.models import Expense, Group, Item, Member, PayerShare, Settlement, Split

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


# ---------------------------------------------------------------------------
# Expenses
# ---------------------------------------------------------------------------
def create_expense(conn, expense: Expense) -> Expense:
    """Save an expense with its payers, splits and items in ONE transaction.

    Either everything is saved or nothing is (atomicity). On any error the
    changes are rolled back and the error is raised again.
    """
    try:
        cur = conn.execute(
            """INSERT INTO expenses
               (group_id, title, category, expense_date, currency,
                original_amount, exchange_rate, base_amount, split_method)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                expense.group_id, expense.title, expense.category,
                expense.expense_date, expense.currency,
                expense.original_amount, expense.exchange_rate,
                expense.base_amount, expense.split_method,
            ),
        )
        expense_id = cur.lastrowid

        for payer in expense.payers:
            conn.execute(
                "INSERT INTO expense_payers (expense_id, member_id, amount_paid) "
                "VALUES (?, ?, ?)",
                (expense_id, payer.member_id, payer.amount_paid),
            )

        for split in expense.splits:
            conn.execute(
                "INSERT INTO expense_splits "
                "(expense_id, member_id, share_amount, percentage) "
                "VALUES (?, ?, ?, ?)",
                (expense_id, split.member_id, split.share_amount, split.percentage),
            )

        for item in expense.items:
            item_cur = conn.execute(
                "INSERT INTO items (expense_id, name, amount) VALUES (?, ?, ?)",
                (expense_id, item.name, item.amount),
            )
            for member_id in item.consumer_ids:
                conn.execute(
                    "INSERT INTO item_consumers (item_id, member_id) VALUES (?, ?)",
                    (item_cur.lastrowid, member_id),
                )

        conn.commit()  # only now does anything become permanent
    except Exception:
        conn.rollback()  # undo every insert above
        raise            # let the caller know the save failed

    return get_expense(conn, expense_id)


def get_expense(conn, expense_id: int) -> Expense | None:
    """Return one expense with its payers, splits and items, or None."""
    row = conn.execute(
        "SELECT * FROM expenses WHERE id = ?", (expense_id,)
    ).fetchone()
    if row is None:
        return None

    expense = Expense.from_row(row)

    expense.payers = [
        PayerShare.from_row(r)
        for r in conn.execute(
            "SELECT * FROM expense_payers WHERE expense_id = ? ORDER BY id",
            (expense_id,),
        )
    ]
    expense.splits = [
        Split.from_row(r)
        for r in conn.execute(
            "SELECT * FROM expense_splits WHERE expense_id = ? ORDER BY id",
            (expense_id,),
        )
    ]

    items = [
        Item.from_row(r)
        for r in conn.execute(
            "SELECT * FROM items WHERE expense_id = ? ORDER BY id", (expense_id,)
        )
    ]
    for item in items:
        item.consumer_ids = [
            r["member_id"]
            for r in conn.execute(
                "SELECT member_id FROM item_consumers WHERE item_id = ? "
                "ORDER BY member_id",
                (item.id,),
            )
        ]
    expense.items = items

    return expense


def list_expenses(conn, group_id: int) -> list[Expense]:
    """All expenses of a group, newest date first (ties: newest id first)."""
    ids = [
        r["id"]
        for r in conn.execute(
            "SELECT id FROM expenses WHERE group_id = ? "
            "ORDER BY expense_date DESC, id DESC",
            (group_id,),
        )
    ]
    return [get_expense(conn, expense_id) for expense_id in ids]


# ---------------------------------------------------------------------------
# Settlements
# ---------------------------------------------------------------------------
def list_settlements(conn, group_id: int) -> list[Settlement]:
    rows = conn.execute(
        "SELECT * FROM settlements WHERE group_id = ? ORDER BY id", (group_id,)
    )
    return [Settlement.from_row(r) for r in rows]


def get_settlement(conn, settlement_id: int) -> Settlement | None:
    row = conn.execute(
        "SELECT * FROM settlements WHERE id = ?", (settlement_id,)
    ).fetchone()
    return Settlement.from_row(row) if row else None


def _log(conn, s_id, group_id, from_id, to_id, amount, event):
    conn.execute(
        "INSERT INTO settlement_history "
        "(group_id, settlement_id, from_member_id, to_member_id, amount, event) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (group_id, s_id, from_id, to_id, amount, event),
    )


def replace_pending_settlements(conn, group_id: int, payments) -> list[Settlement]:
    """Delete the old Pending plan and save a new one (one transaction)."""
    try:
        conn.execute(
            "DELETE FROM settlements WHERE group_id = ? AND status = 'Pending'",
            (group_id,),
        )
        for from_id, to_id, amount in payments:
            cur = conn.execute(
                "INSERT INTO settlements "
                "(group_id, from_member_id, to_member_id, amount) VALUES (?, ?, ?, ?)",
                (group_id, from_id, to_id, amount),
            )
            _log(conn, cur.lastrowid, group_id, from_id, to_id, amount, "Generated")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return [s for s in list_settlements(conn, group_id) if s.status == "Pending"]


def set_settlement_status(conn, settlement_id: int, completed: bool) -> Settlement | None:
    """Mark a settlement Completed (True) or Pending again (False)."""
    s = get_settlement(conn, settlement_id)
    if s is None:
        return None
    try:
        if completed:
            conn.execute(
                "UPDATE settlements SET status = 'Completed', "
                "completed_at = CURRENT_TIMESTAMP WHERE id = ?", (settlement_id,))
        else:
            conn.execute(
                "UPDATE settlements SET status = 'Pending', completed_at = NULL "
                "WHERE id = ?", (settlement_id,))
        _log(conn, s.id, s.group_id, s.from_member_id, s.to_member_id, s.amount,
             "Completed" if completed else "Reopened")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return get_settlement(conn, settlement_id)


def list_settlement_history(conn, group_id: int) -> list[dict]:
    rows = conn.execute(
        """SELECT h.event_at, h.event, h.amount,
                  f.name AS from_name, t.name AS to_name
           FROM settlement_history h
           JOIN members f ON f.id = h.from_member_id
           JOIN members t ON t.id = h.to_member_id
           WHERE h.group_id = ? ORDER BY h.id DESC""",
        (group_id,),
    )
    return [dict(r) for r in rows]


def update_expense_details(conn, expense_id: int, title: str, category: str,
                           expense_date: str) -> Expense | None:
    """Change only the title, category and date. Amounts are untouched."""
    cur = conn.execute(
        "UPDATE expenses SET title = ?, category = ?, expense_date = ? WHERE id = ?",
        (title, category, expense_date, expense_id),
    )
    conn.commit()
    return get_expense(conn, expense_id) if cur.rowcount else None


def delete_expense(conn, expense_id: int) -> bool:
    """Delete an expense. Its payers, splits and items go with it (CASCADE)."""
    cur = conn.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
    conn.commit()
    return cur.rowcount > 0