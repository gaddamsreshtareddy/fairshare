"""FairShare: Expense History page (list, details, edit, delete)."""

from datetime import date

import streamlit as st

from data.models import format_money
from logic.validators import CATEGORIES, ValidationError
from services import expense_service as es
from services import group_service as gs
from ui.components import db_session, flash, render_sidebar, require_open_group, show_flash

st.set_page_config(page_title="Expenses - FairShare", page_icon="💸", layout="wide")
render_sidebar()

st.title("🧾 Expenses")
group = require_open_group()
show_flash()

with db_session() as conn:
    expenses = es.list_expenses(conn, group.id)
    members = gs.list_members(conn, group.id)  # include inactive, for names

names = {m.id: m.name for m in members}
currency = group.base_currency
METHODS = {"equal": "Equal", "custom": "Custom",
           "percentage": "Percentage", "item": "Item-based"}

if not expenses:
    st.info("No expenses yet. Add the first one on the Add Expense page.")
    st.stop()

col1, col2 = st.columns(2)
col1.metric("Expenses", len(expenses))
col2.metric("Total spending", format_money(sum(e.base_amount for e in expenses), currency))


def original_text(e):
    """Show the original amount and rate for foreign-currency expenses."""
    if e.currency == currency:
        return ""
    return f"{format_money(e.original_amount, e.currency)} @ {e.exchange_rate:g}"


st.dataframe(
    [
        {
            "Date": e.expense_date,
            "Expense": e.title,
            "Amount": format_money(e.base_amount, currency),
            "Original": original_text(e),
            "Category": e.category,
            "Split": METHODS[e.split_method],
            "Paid by": ", ".join(names[p.member_id] for p in e.payers),
        }
        for e in expenses
    ],
    hide_index=True,
    use_container_width=True,
)

# ---------------------------------------------------------------------------
# Detail view
# ---------------------------------------------------------------------------
st.divider()
st.subheader("Expense details")

by_id = {e.id: e for e in expenses}
chosen_id = st.selectbox(
    "Choose an expense",
    list(by_id),
    format_func=lambda i: f"{by_id[i].expense_date} · {by_id[i].title} · "
                          f"{format_money(by_id[i].base_amount, currency)}",
)
exp = by_id[chosen_id]

st.markdown(f"**{exp.title}**: {format_money(exp.base_amount, currency)} "
            f"({exp.category}, {METHODS[exp.split_method]} split)")
if exp.currency != currency:
    st.caption(f"Entered as {format_money(exp.original_amount, exp.currency)} "
               f"at 1 {exp.currency} = {exp.exchange_rate:g} {currency}.")

left, right = st.columns(2)
with left:
    st.markdown("**Paid by**")
    for p in exp.payers:
        st.write(f"- {names[p.member_id]}: {format_money(p.amount_paid, currency)}")
with right:
    st.markdown("**Share (who owes)**")
    for s in exp.splits:
        extra = f" ({s.percentage:g}%)" if s.percentage is not None else ""
        st.write(f"- {names[s.member_id]}: {format_money(s.share_amount, currency)}{extra}")

if exp.items:
    st.markdown("**Items**")
    for item in exp.items:
        who = ", ".join(names[c] for c in item.consumer_ids)
        st.write(f"- {item.name}: {format_money(item.amount, currency)} → {who}")

# ---------------------------------------------------------------------------
# Edit / delete the selected expense
# ---------------------------------------------------------------------------
st.divider()
st.subheader("Edit or delete this expense")
st.caption("To change amounts, payers or the split, delete the expense and add it again.")

edit_col, delete_col = st.columns(2, gap="large")

with edit_col:
    with st.form(f"edit_form_{exp.id}"):
        new_title = st.text_input("Title", value=exp.title)
        new_category = st.selectbox("Category", CATEGORIES,
                                    index=CATEGORIES.index(exp.category))
        new_date = st.date_input("Date", value=date.fromisoformat(exp.expense_date))
        save_clicked = st.form_submit_button("Save changes")

with delete_col:
    with st.form(f"delete_form_{exp.id}"):
        sure = st.checkbox("Yes, delete this expense")
        delete_clicked = st.form_submit_button("Delete expense")
    st.caption("Deleting also clears the pending settlement plan. Generate it again afterwards.")

try:
    if save_clicked:
        with db_session() as conn:
            es.update_expense_details(conn, exp.id, new_title, new_category, new_date)
        flash("Expense updated.")
        st.rerun()
    elif delete_clicked:
        if not sure:
            st.warning("Tick the box first to confirm.")
        else:
            with db_session() as conn:
                es.delete_expense(conn, exp.id)
            flash(f"Expense '{exp.title}' deleted.")
            st.rerun()
except ValidationError as error:
    st.error(str(error))