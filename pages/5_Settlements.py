"""FairShare: Settlements page (who pays whom)."""

import streamlit as st

from data.models import format_money
from logic.validators import ValidationError
from services import group_service as gs
from services import settlement_service as ss
from ui.components import db_session, flash, render_sidebar, require_open_group, show_flash

st.set_page_config(page_title="Settlements - FairShare", page_icon="💸", layout="wide")
render_sidebar()

st.title("🤝 Settlements")
group = require_open_group()
show_flash()
currency = group.base_currency

with db_session() as conn:
    nets = ss.current_nets(conn, group.id)
    settlements = ss.list_settlements(conn, group.id)
    members = gs.list_members(conn, group.id)
    history = ss.history(conn, group.id)

names = {m.id: m.name for m in members}
pending = [s for s in settlements if s.status == "Pending"]
completed = [s for s in settlements if s.status == "Completed"]
people_owing = sum(1 for v in nets.values() if v != 0)

if not any(nets.values()) and not settlements:
    st.info("Nothing to settle yet. Add expenses first.")
    st.stop()

c1, c2, c3 = st.columns(3)
c1.metric("People with a balance", people_owing)
c2.metric("Pending payments", len(pending))
c3.metric("Completed payments", len(completed))

if st.button("Generate / refresh settlement plan", type="primary"):
    try:
        with db_session() as conn:
            plan = ss.generate_plan(conn, group.id)
        flash(f"Plan generated: {len(plan)} payment(s) needed." if plan
              else "Everyone is settled. No payments needed.")
        st.rerun()
    except ValidationError as error:
        st.error(str(error))

st.caption("Uses the exact minimum-transaction method for up to 12 people, "
           "and the greedy method for larger groups. Completed payments are "
           "counted as already paid.")

# ---------------------------------------------------------------------------
st.divider()
st.subheader("Pending: who pays whom")
if not pending:
    st.info("No pending payments. Click the button above to generate the plan.")
for s in pending:
    col_a, col_b = st.columns([4, 1])
    col_a.write(f"🔴 **{names[s.from_member_id]}** pays **{names[s.to_member_id]}** "
                f"{format_money(s.amount, currency)}")
    if col_b.button("Mark completed", key=f"done_{s.id}"):
        try:
            with db_session() as conn:
                ss.mark_completed(conn, s.id)
            flash("Marked as completed.")
            st.rerun()
        except ValidationError as error:
            st.error(str(error))

st.subheader("Completed")
if not completed:
    st.caption("None yet.")
for s in completed:
    col_a, col_b = st.columns([4, 1])
    col_a.write(f"🟢 {names[s.from_member_id]} paid {names[s.to_member_id]} "
                f"{format_money(s.amount, currency)} ({s.completed_at})")
    if col_b.button("Reopen", key=f"reopen_{s.id}"):
        with db_session() as conn:
            ss.reopen(conn, s.id)
        flash("Moved back to pending.")
        st.rerun()

# ---------------------------------------------------------------------------
st.divider()
st.subheader("Settlement history")
if history:
    st.dataframe(
        [{"When": h["event_at"], "Event": h["event"],
          "From": h["from_name"], "To": h["to_name"],
          "Amount": format_money(h["amount"], currency)} for h in history],
        hide_index=True, use_container_width=True,
    )
else:
    st.caption("No history yet.")