"""Application layer: settlement plans and history."""

from data import repositories as repo
from logic.settlement_algorithm import settle
from logic.validators import ValidationError
from services import expense_service, group_service


def current_nets(conn, group_id):
    """Net balance per member after counting Completed settlements as paid."""
    balances = expense_service.get_balances(conn, group_id)
    nets = {m: b["net"] for m, b in balances.items()}
    for s in repo.list_settlements(conn, group_id):
        if s.status == "Completed":
            nets[s.from_member_id] += s.amount   # they paid, so they owe less
            nets[s.to_member_id] -= s.amount     # they received, so they are owed less
    return nets


def generate_plan(conn, group_id):
    """Create a fresh Pending plan from the current balances."""
    group_service.get_group(conn, group_id)
    payments = settle(current_nets(conn, group_id))
    return repo.replace_pending_settlements(conn, group_id, payments)


def list_settlements(conn, group_id):
    return repo.list_settlements(conn, group_id)


def mark_completed(conn, settlement_id):
    s = repo.set_settlement_status(conn, settlement_id, True)
    if s is None:
        raise ValidationError("That settlement no longer exists.")
    return s


def reopen(conn, settlement_id):
    s = repo.set_settlement_status(conn, settlement_id, False)
    if s is None:
        raise ValidationError("That settlement no longer exists.")
    return s


def history(conn, group_id):
    return repo.list_settlement_history(conn, group_id)