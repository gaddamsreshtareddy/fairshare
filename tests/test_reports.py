from data.models import Expense, Group, Member, PayerShare, Settlement, Split
from reports.csv_export import balances_csv, expenses_csv
from reports.pdf_report import build_pdf

NAMES = {1: "A", 2: "B"}
EXPENSE = Expense(
    id=1, group_id=1, title="Dinner", expense_date="2025-01-01", currency="INR",
    original_amount=120000, base_amount=120000, split_method="equal",
    payers=[PayerShare(member_id=1, amount_paid=120000)],
    splits=[Split(member_id=1, share_amount=60000),
            Split(member_id=2, share_amount=60000)],
)
BALANCES = {1: {"paid": 120000, "owed": 60000, "net": 60000},
            2: {"paid": 0, "owed": 60000, "net": -60000}}


def test_expenses_csv_has_header_and_row():
    lines = expenses_csv([EXPENSE], NAMES, "INR").strip().splitlines()
    assert lines[0].startswith("Date,Expense,Category")
    assert "1200.00" in lines[1] and "Dinner" in lines[1]


def test_balances_csv_rows():
    lines = balances_csv(BALANCES, NAMES, "INR").strip().splitlines()
    assert len(lines) == 3
    assert "600.00" in lines[1]
    assert "-600.00" in lines[2]


def test_csv_blocks_formula_injection():
    bad = Expense(id=2, group_id=1, title="=1+1", expense_date="2025-01-01",
                  currency="INR", original_amount=100, base_amount=100,
                  split_method="equal")
    assert "'=1+1" in expenses_csv([bad], NAMES, "INR")


def test_pdf_is_a_valid_pdf():
    group = Group(id=1, name="Trip <b>", base_currency="INR")
    members = [Member(id=1, group_id=1, name="A"), Member(id=2, group_id=1, name="B")]
    settlements = [Settlement(id=1, group_id=1, from_member_id=2, to_member_id=1,
                              amount=60000)]
    pdf = build_pdf(group, members, [EXPENSE], BALANCES, settlements, NAMES)
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 1000


def test_pdf_works_with_no_data():
    group = Group(id=1, name="Empty", base_currency="INR")
    assert build_pdf(group, [], [], {}, [], {}).startswith(b"%PDF")