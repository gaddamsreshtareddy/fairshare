"""FairShare: Add Expense page."""

from datetime import date

import streamlit as st

from data.models import format_money, to_minor
from logic.splitting import equal_split
from logic.validators import CATEGORIES, ValidationError
from services import expense_service as es
from services import group_service as gs
from ui.components import (
    db_session,
    flash,
    render_sidebar,
    require_open_group,
    show_flash,
)

st.set_page_config(page_title="Add Expense - FairShare", page_icon="💸", layout="wide")
render_sidebar()

st.title("➕ Add Expense")
group = require_open_group()  # stops the page if no group is open
show_flash()

with db_session() as conn:
    members = gs.list_members(conn, group.id, active_only=True)

if not members:
    st.warning("This group has no active members. Add some in Group Settings first.")
    st.stop()

names = {m.id: m.name for m in members}  # {member_id: name}
n = st.session_state.get("expense_form_n", 0)  # form counter, used in widget keys


title = st.text_input(
    "Expense title",
    placeholder="e.g. Dinner",
    key=f"title_{n}",
)

col1, col2, col3 = st.columns(3)

expense_date = col1.date_input(
    "Date",
    value=date.today(),
    key=f"date_{n}",
)

category = col2.selectbox(
    "Category",
    CATEGORIES,
    key=f"category_{n}",
)

amount = col3.number_input(
    f"Amount ({group.base_currency})",
    min_value=0.0,
    step=0.01,
    format="%.2f",
    key=f"amount_{n}",
)

total = to_minor(amount)

payer_id = st.selectbox(
    "Paid by",
    list(names),
    format_func=names.get,
    key=f"payer_{n}",
)

st.selectbox(
    "Split method",
    ["Equal"],
    key=f"method_{n}",
)

participants = st.multiselect(
    "Split between",
    list(names),
    default=list(names),
    format_func=names.get,
    key=f"participants_{n}",
)


st.divider()
st.subheader("Preview")

shares = None

if total <= 0:
    st.info("Enter an amount greater than zero.")
elif not participants:
    st.info("Choose at least one person to split between.")
else:
    try:
        shares = equal_split(total, participants)
    except ValidationError as error:
        st.error(str(error))

if shares:
    currency = group.base_currency

    st.markdown(
        f"**Expense:** {title.strip() or '(no title yet)'}"
    )

    st.markdown(
        f"**Total:** {format_money(total, currency)}"
    )

    st.markdown("**Paid by:**")
    st.write(
        f"- {names[payer_id]}: "
        f"{format_money(total, currency)}"
    )

    st.markdown("**Share:**")

    for member_id, share in shares.items():
        st.write(
            f"- {names[member_id]}: "
            f"{format_money(share, currency)}"
        )

if st.button(
    "Save expense",
    type="primary",
    disabled=shares is None,
    key=f"save_{n}",
):
    try:
        with db_session() as conn:
            saved = es.add_expense(
                conn,
                group.id,
                title,
                category,
                expense_date,
                payers={payer_id: total},
                split_method="equal",
                total=total,
                member_ids=participants,
            )

        flash(f"Expense '{saved.title}' saved.")
        st.session_state["expense_form_n"] = n + 1
        st.rerun()

    except ValidationError as error:
        st.error(str(error))