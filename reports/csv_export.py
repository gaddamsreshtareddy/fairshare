"""CSV export (reports layer). Amounts are written in rupees, e.g. 1200.00."""

import csv
import io

from data.models import from_minor


def _money(minor):
    return f"{from_minor(minor):.2f}"


def _text(value):
    """Stop spreadsheets from running a cell as a formula (CSV injection)."""
    value = str(value)
    return "'" + value if value[:1] in ("=", "+", "-", "@") else value


def expenses_csv(expenses, names, currency):
    """One row per expense. Returns the CSV as text."""
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["Date", "Expense", "Category", "Split method",
                     f"Amount ({currency})", "Paid by", "Shares"])
    for e in expenses:
        paid_by = "; ".join(f"{names[p.member_id]} {_money(p.amount_paid)}"
                            for p in e.payers)
        shares = "; ".join(f"{names[s.member_id]} {_money(s.share_amount)}"
                           for s in e.splits)
        writer.writerow([e.expense_date, _text(e.title), e.category, e.split_method,
                         _money(e.base_amount), _text(paid_by), _text(shares)])
    return out.getvalue()


def balances_csv(balances, names, currency):
    """One row per member with paid, owed and net. Returns the CSV as text."""
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["Member", f"Paid ({currency})", f"Owed ({currency})",
                     f"Net ({currency})"])
    for member_id, b in balances.items():
        writer.writerow([_text(names[member_id]), _money(b["paid"]),
                         _money(b["owed"]), _money(b["net"])])
    return out.getvalue()