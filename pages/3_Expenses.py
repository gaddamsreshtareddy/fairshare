"""FairShare: Expense History page."""

import streamlit as st

from data.models import format_money
from services import expense_service as es
from services import group_service as gs
from ui.components import db_session, render_sidebar, require_open_group, show_flash

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

st.dataframe(
    [
        {
            "Date": e.expense_date,
            "Expense": e.title,
            "Amount": format_money(e.base_amount, currency),
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