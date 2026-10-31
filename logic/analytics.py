"""Analytics calculations (business logic layer). Pure Python, no database.

All amounts are integer paise.
"""


def spending_by_category(expenses):
    """{category: total_paise}, biggest first."""
    totals = {}
    for e in expenses:
        totals[e.category] = totals.get(e.category, 0) + e.base_amount
    return dict(sorted(totals.items(), key=lambda kv: (-kv[1], kv[0])))


def spending_by_date(expenses):
    """{date_text: total_paise}, oldest date first."""
    totals = {}
    for e in expenses:
        totals[e.expense_date] = totals.get(e.expense_date, 0) + e.base_amount
    return dict(sorted(totals.items()))


def top_category(expenses):
    """(category, total) with the highest spending, or None if no expenses."""
    totals = spending_by_category(expenses)
    return next(iter(totals.items())) if totals else None


def top_contributor(balances):
    """(member_id, paid) for the member who paid the most, or None.

    balances is the {member_id: {"paid", "owed", "net"}} dict from calculate_balances.
    Ties go to the smaller member id.
    """
    paid = [(m, b["paid"]) for m, b in balances.items() if b["paid"] > 0]
    if not paid:
        return None
    return min(paid, key=lambda x: (-x[1], x[0]))


def top_spender(balances):
    """(member_id, owed) for the member with the biggest share of costs, or None."""
    owed = [(m, b["owed"]) for m, b in balances.items() if b["owed"] > 0]
    if not owed:
        return None
    return min(owed, key=lambda x: (-x[1], x[0]))