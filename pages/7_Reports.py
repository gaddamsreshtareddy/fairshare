"""FairShare: Reports page (PDF and CSV export)."""

import streamlit as st

from reports.csv_export import balances_csv, expenses_csv
from reports.pdf_report import build_pdf
from services import expense_service as es
from services import group_service as gs
from services import settlement_service as ss
from ui.components import db_session, render_sidebar, require_open_group, show_flash

st.set_page_config(page_title="Reports - FairShare", page_icon="💸", layout="wide")
render_sidebar()

st.title("📄 Reports & Export")
group = require_open_group()
show_flash()

with db_session() as conn:
    members = gs.list_members(conn, group.id)
    expenses = es.list_expenses(conn, group.id)
    balances = es.get_balances(conn, group.id)
    settlements = ss.list_settlements(conn, group.id)

names = {m.id: m.name for m in members}
safe_name = "".join(ch if ch.isalnum() else "_" for ch in group.name)

if not expenses:
    st.info("No expenses yet. Add some to export a report.")
    st.stop()

st.subheader("PDF report")
st.caption("Group summary, members, expenses, shares, payments, balances and settlements.")
st.download_button(
    "Download PDF report",
    data=build_pdf(group, members, expenses, balances, settlements, names),
    file_name=f"fairshare_{safe_name}.pdf",
    mime="application/pdf",
    type="primary",
)

st.divider()
st.subheader("CSV export")
c1, c2 = st.columns(2)
c1.download_button(
    "Download expenses (CSV)",
    data=expenses_csv(expenses, names, group.base_currency),
    file_name=f"fairshare_{safe_name}_expenses.csv",
    mime="text/csv",
)
c2.download_button(
    "Download balances (CSV)",
    data=balances_csv(balances, names, group.base_currency),
    file_name=f"fairshare_{safe_name}_balances.csv",
    mime="text/csv",
)