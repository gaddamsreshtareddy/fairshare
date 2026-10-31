"""FairShare: Analytics page (Plotly charts)."""

import pandas as pd
import plotly.express as px
import streamlit as st

from data.models import from_minor
from logic.analytics import spending_by_category, spending_by_date
from services import expense_service as es
from services import group_service as gs
from ui.components import db_session, render_sidebar, require_open_group, show_flash

st.set_page_config(page_title="Analytics - FairShare", page_icon="💸", layout="wide")
render_sidebar()

st.title("📈 Analytics")
group = require_open_group()
show_flash()
currency = group.base_currency

with db_session() as conn:
    expenses = es.list_expenses(conn, group.id)
    balances = es.get_balances(conn, group.id)
    members = gs.list_members(conn, group.id)

if not expenses:
    st.info("No expenses yet. Add some to see charts.")
    st.stop()

names = {m.id: m.name for m in members}

left, right = st.columns(2)

with left:
    st.subheader("Spending by category")
    by_cat = spending_by_category(expenses)
    df_cat = pd.DataFrame({"Category": list(by_cat),
                           "Amount": [float(from_minor(v)) for v in by_cat.values()]})
    st.plotly_chart(px.pie(df_cat, names="Category", values="Amount", hole=0.4),
                    use_container_width=True)

with right:
    st.subheader("Paid vs share, by member")
    rows = []
    for m, b in balances.items():
        if b["paid"] or b["owed"]:
            rows.append({"Member": names[m], "Type": "Paid",
                         "Amount": float(from_minor(b["paid"]))})
            rows.append({"Member": names[m], "Type": "Share (owed)",
                         "Amount": float(from_minor(b["owed"]))})
    st.plotly_chart(px.bar(pd.DataFrame(rows), x="Member", y="Amount",
                           color="Type", barmode="group"),
                    use_container_width=True)

st.subheader("Spending over time")
by_date = spending_by_date(expenses)
df_date = pd.DataFrame({"Date": list(by_date),
                        "Amount": [float(from_minor(v)) for v in by_date.values()]})
st.plotly_chart(px.bar(df_date, x="Date", y="Amount"), use_container_width=True)

st.caption(f"All amounts in {currency}.")