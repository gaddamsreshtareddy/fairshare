"""FairShare: Dashboard page."""

import streamlit as st

from data.models import format_money
from logic.analytics import top_category, top_contributor, top_spender
from services import expense_service as es
from services import group_service as gs
from services import settlement_service as ss
from ui.components import db_session, render_sidebar, require_open_group, show_flash

st.set_page_config(page_title="Dashboard - FairShare", page_icon="💸", layout="wide")
render_sidebar()

st.title("📊 Dashboard")
group = require_open_group()
show_flash()
currency = group.base_currency

with db_session() as conn:
    summary = gs.get_group_summary(conn, group.id)
    expenses = es.list_expenses(conn, group.id)
    balances = es.get_balances(conn, group.id)
    settlements = ss.list_settlements(conn, group.id)
    members = gs.list_members(conn, group.id)

names = {m.id: m.name for m in members}
pending = sum(1 for s in settlements if s.status == "Pending")
completed = sum(1 for s in settlements if s.status == "Completed")

st.subheader(group.name)
c1, c2, c3 = st.columns(3)
c1.metric("Total spending", format_money(sum(e.base_amount for e in expenses), currency))
c2.metric("Members", summary.active_member_count)
c3.metric("Expenses", len(expenses))

c4, c5, c6 = st.columns(3)
c4.metric("Pending settlements", pending)
c5.metric("Completed settlements", completed)
c6.metric("Base currency", currency)

if not expenses:
    st.info("No expenses yet. Add your first one to see insights here.")
else:
    st.divider()
    st.subheader("Highlights")
    h1, h2, h3 = st.columns(3)
    cat = top_category(expenses)
    contrib = top_contributor(balances)
    spender = top_spender(balances)
    h1.metric("Highest spending category", cat[0], format_money(cat[1], currency),
              delta_color="off")
    h2.metric("Highest contributor (paid most)", names[contrib[0]],
              format_money(contrib[1], currency), delta_color="off")
    h3.metric("Highest spender (biggest share)", names[spender[0]],
              format_money(spender[1], currency), delta_color="off")

    st.divider()
    st.subheader("Your financial summary")
    st.dataframe(
        [{"Member": names[m], "Paid": format_money(b["paid"], currency),
          "Owes (share)": format_money(b["owed"], currency),
          "Net": format_money(b["net"], currency)}
         for m, b in balances.items() if b["paid"] or b["owed"]],
        hide_index=True, use_container_width=True,
    )

st.divider()
st.subheader("Quick actions")
q1, q2, q3, q4 = st.columns(4)
q1.page_link("pages/2_Add_Expense.py", label="Add expense", icon="➕")
q2.page_link("pages/4_Balances.py", label="Balances", icon="⚖️")
q3.page_link("pages/5_Settlements.py", label="Settlements", icon="🤝")
q4.page_link("pages/6_Analytics.py", label="Analytics", icon="📈")