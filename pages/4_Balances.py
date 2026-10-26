"""FairShare: Balances page."""

import streamlit as st

from data.models import format_money
from services import expense_service as es
from services import group_service as gs
from ui.components import db_session, render_sidebar, require_open_group, show_flash

st.set_page_config(page_title="Balances - FairShare", page_icon="💸", layout="wide")
render_sidebar()

st.title("⚖️ Balances")
group = require_open_group()
show_flash()

with db_session() as conn:
    balances = es.get_balances(conn, group.id)
    members = gs.list_members(conn, group.id)

currency = group.base_currency

# Show active members, plus inactive ones who still have activity.
shown = [m for m in members
         if m.is_active or balances[m.id]["paid"] or balances[m.id]["owed"]]

if not any(b["paid"] or b["owed"] for b in balances.values()):
    st.info("No expenses yet, so everyone is settled. Add an expense first.")
    st.stop()


def describe(net):
    if net > 0:
        return f"Gets {format_money(net, currency)}"
    if net < 0:
        return f"Owes {format_money(abs(net), currency)}"
    return "All settled"


st.subheader("Who gets and who owes")
for m in shown:
    net = balances[m.id]["net"]
    icon = "🟢" if net > 0 else "🔴" if net < 0 else "⚪"
    st.write(f"{icon} **{m.name}** → {describe(net)}")

st.divider()
st.subheader("Details")
st.dataframe(
    [
        {
            "Member": m.name,
            "Total paid": format_money(balances[m.id]["paid"], currency),
            "Total owed (share)": format_money(balances[m.id]["owed"], currency),
            "Net balance": format_money(balances[m.id]["net"], currency),
            "Status": describe(balances[m.id]["net"]),
        }
        for m in shown
    ],
    hide_index=True,
    use_container_width=True,
)

total_net = sum(b["net"] for b in balances.values())
st.caption("✅ All balances add up to zero." if total_net == 0
           else f"⚠️ Balances are off by {total_net} paise. This is a bug.")