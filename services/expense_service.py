"""Application layer: expense operations.

Validates input, calls the splitting logic, builds the Expense model and
saves it through the repository. No SQL and no split math lives here.
"""

from datetime import date
from decimal import Decimal
from logic.balances import calculate_balances
from data import repositories as repo
from data.models import Expense, Item, PayerShare, Split
from logic.splitting import (
    custom_split,
    equal_split,
    item_split,
    percentage_split,
    validate_payers,
)
from logic.validators import CATEGORIES, ValidationError, clean_text
from services import group_service


def _check_members_in_group(conn, group_id, member_ids):
    """Every id must be a real member of THIS group."""
    for member_id in member_ids:
        member = repo.get_member(conn, member_id)
        if member is None or member.group_id != group_id:
            raise ValidationError("Every person must be a member of this group.")


def add_expense(conn, group_id, title, category, expense_date, payers,
                split_method, total=None, member_ids=None, shares=None,
                percentages=None, items=None) -> Expense:
    """Validate and save one expense. All money is in integer paise.

    payers:      {member_id: paise_paid}
    equal:       total + member_ids
    custom:      total + shares {member_id: paise}
    percentage:  total + percentages {member_id: "33.34"}
    item:        items [(name, amount_paise, [consumer_ids]), ...]
                 (the total is the sum of the items)
    """
    group = group_service.get_group(conn, group_id)  # raises if missing

    clean_title = clean_text(title)
    if not clean_title:
        raise ValidationError("Title is required.")
    if category not in CATEGORIES:
        raise ValidationError(f"Category must be one of: {', '.join(CATEGORIES)}.")
    if isinstance(expense_date, date):
        expense_date = expense_date.isoformat()
    try:
        date.fromisoformat(str(expense_date))
    except ValueError:
        raise ValidationError("Date is not valid.") from None

    percent_by_member = {}
    item_models = []

    if split_method == "equal":
        split_amounts = equal_split(total, list(member_ids or []))
    elif split_method == "custom":
        split_amounts = custom_split(total, shares or {})
    elif split_method == "percentage":
        split_amounts = percentage_split(total, percentages or {})
        percent_by_member = {
            m: float(Decimal(str(p))) for m, p in (percentages or {}).items()
        }
    elif split_method == "item":
        items = items or []
        total, split_amounts = item_split([(amt, cons) for _, amt, cons in items])
        item_models = [
            Item(name=clean_text(name) or "Item", amount=amt, consumer_ids=list(cons))
            for name, amt, cons in items
        ]
    else:
        raise ValidationError("Choose a split method.")

    payer_amounts = validate_payers(total, payers)
    _check_members_in_group(conn, group_id, list(payer_amounts) + list(split_amounts))

    expense = Expense(
        id=None,
        group_id=group_id,
        title=clean_title,
        expense_date=str(expense_date),
        currency=group.base_currency,
        original_amount=total,
        base_amount=total,
        split_method=split_method,
        category=category,
        exchange_rate=1.0,
        payers=[PayerShare(member_id=m, amount_paid=a) for m, a in payer_amounts.items()],
        splits=[
            Split(member_id=m, share_amount=a, percentage=percent_by_member.get(m))
            for m, a in split_amounts.items()
        ],
        items=item_models,
    )
    return repo.create_expense(conn, expense)


def get_expense(conn, expense_id):
    expense = repo.get_expense(conn, expense_id)
    if expense is None:
        raise ValidationError("That expense no longer exists.")
    return expense


def list_expenses(conn, group_id):
    return repo.list_expenses(conn, group_id)

def get_balances(conn, group_id):
    """Return {member_id: {"paid", "owed", "net"}} for the whole group."""
    group_service.get_group(conn, group_id)  # raises if the group is missing
    expenses = repo.list_expenses(conn, group_id)
    members = repo.list_members(conn, group_id)
    return calculate_balances(expenses, [m.id for m in members])


def update_expense_details(conn, expense_id, title, category, expense_date):
    """Edit the title, category and date of a saved expense."""
    get_expense(conn, expense_id)  # raises if it no longer exists
    clean_title = clean_text(title)
    if not clean_title:
        raise ValidationError("Title is required.")
    if category not in CATEGORIES:
        raise ValidationError(f"Category must be one of: {', '.join(CATEGORIES)}.")
    if isinstance(expense_date, date):
        expense_date = expense_date.isoformat()
    try:
        date.fromisoformat(str(expense_date))
    except ValueError:
        raise ValidationError("Date is not valid.") from None
    return repo.update_expense_details(conn, expense_id, clean_title, category,
                                       str(expense_date))


def delete_expense(conn, expense_id):
    """Delete an expense and clear the now out-of-date pending settlement plan."""
    expense = get_expense(conn, expense_id)
    repo.delete_expense(conn, expense_id)
    repo.replace_pending_settlements(conn, expense.group_id, [])