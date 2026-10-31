import pytest

from logic.validators import ValidationError
from services import expense_service as es
from services import group_service as gs
from services import settlement_service as ss


@pytest.fixture
def setup(conn):
    g = gs.create_group(conn, "Trip")
    a, b, c = (gs.add_member(conn, g.id, n).id for n in "ABC")
    e = es.add_expense(conn, g.id, "Dinner", "Food", "2025-01-01",
                       payers={a: 120000}, split_method="equal",
                       total=120000, member_ids=[a, b, c])
    return g, e, a, b, c


def test_edit_changes_details_but_not_amounts(conn, setup):
    g, e, *_ = setup
    updated = es.update_expense_details(conn, e.id, "  Team  Dinner ", "Hotel", "2025-02-02")
    assert updated.title == "Team Dinner"
    assert updated.category == "Hotel"
    assert updated.expense_date == "2025-02-02"
    assert updated.base_amount == 120000
    assert len(updated.splits) == 3


def test_edit_blank_title_rejected_and_changes_nothing(conn, setup):
    g, e, *_ = setup
    with pytest.raises(ValidationError, match="Title"):
        es.update_expense_details(conn, e.id, "  ", "Food", "2025-01-01")
    assert es.get_expense(conn, e.id).title == "Dinner"


def test_edit_bad_date_rejected(conn, setup):
    g, e, *_ = setup
    with pytest.raises(ValidationError):
        es.update_expense_details(conn, e.id, "Dinner", "Food", "2025-13-45")


def test_delete_removes_expense_and_its_rows(conn, setup):
    g, e, *_ = setup
    es.delete_expense(conn, e.id)
    assert es.list_expenses(conn, g.id) == []
    for table in ("expense_payers", "expense_splits"):
        assert conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0


def test_delete_resets_balances_to_zero(conn, setup):
    g, e, a, b, c = setup
    es.delete_expense(conn, e.id)
    balances = es.get_balances(conn, g.id)
    assert all(v["net"] == 0 for v in balances.values())


def test_delete_clears_pending_plan(conn, setup):
    g, e, *_ = setup
    ss.generate_plan(conn, g.id)
    es.delete_expense(conn, e.id)
    assert [s for s in ss.list_settlements(conn, g.id) if s.status == "Pending"] == []


def test_delete_missing_expense_raises(conn):
    with pytest.raises(ValidationError):
        es.delete_expense(conn, 9999)