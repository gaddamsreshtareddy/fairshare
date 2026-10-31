"""FairShare: Add Expense page (four split methods, multiple payers, currencies)."""

from datetime import date
from decimal import Decimal

import streamlit as st

from data.models import format_money, to_minor
from logic.currency import convert, needs_conversion, parse_rate
from logic.splitting import (
    custom_split,
    equal_split,
    item_split,
    percentage_split,
    validate_payers,
)
from logic.validators import CATEGORIES, SUPPORTED_CURRENCIES, ValidationError
from services import expense_service as es
from services import group_service as gs
from services.rate_service import fetch_rate
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
base = group.base_currency


def fill_live_rate(from_cur, to_cur, form_n):
    """Button callback: put a live rate into the rate box."""
    try:
        rate = fetch_rate(from_cur, to_cur)
        st.session_state[f"rate_{form_n}"] = format(rate.quantize(Decimal("0.000001")), "f")
        st.session_state["rate_msg"] = (
            "ok",
            f"Live rate loaded: 1 {from_cur} = "
            f"{format(rate.quantize(Decimal('0.0001')), 'f')} {to_cur}",
        )
    except ValidationError as error:
        st.session_state["rate_msg"] = ("warn", str(error))


# ---------------------------------------------------------------------------
# Part 1: basic fields, split method and currency
# ---------------------------------------------------------------------------
METHODS = {"Equal": "equal", "Custom": "custom",
           "Percentage": "percentage", "Item-based": "item"}

title = st.text_input("Expense title", placeholder="e.g. Dinner", key=f"title_{n}")

col1, col2, col3, col4 = st.columns(4)
expense_date = col1.date_input("Date", value=date.today(), key=f"date_{n}")
category = col2.selectbox("Category", CATEGORIES, key=f"category_{n}")
method = METHODS[col3.selectbox("Split method", list(METHODS), key=f"method_{n}")]
currency = col4.selectbox(
    "Currency", SUPPORTED_CURRENCIES,
    index=SUPPORTED_CURRENCIES.index(base), key=f"currency_{n}",
)

rate_text = None
rate_error = None
if needs_conversion(currency, base):
    r1, r2 = st.columns([3, 1])
    rate_text = r1.text_input(
        f"Exchange rate: 1 {currency} = ? {base}",
        placeholder="e.g. 83.25", key=f"rate_{n}",
    )
    r2.write("")
    r2.button("Fetch live rate", on_click=fill_live_rate,
              args=(currency, base, n), key=f"fetch_{n}")
    msg = st.session_state.pop("rate_msg", None)
    if msg:
        (st.success if msg[0] == "ok" else st.warning)(msg[1])
    try:
        parse_rate(rate_text)
    except ValidationError as error:
        rate_error = str(error)

st.divider()
total = 0
shares = None
split_error = None
participants, shares_in, percents, items_data = [], {}, {}, []

# ---------------------------------------------------------------------------
# Part 2: split details (changes with the method)
# ---------------------------------------------------------------------------
if method == "item":
    st.subheader("Items")
    st.caption("The total is the sum of the items. Add tax or tips as an extra item.")
    count = st.number_input("Number of items", min_value=1, max_value=15,
                            value=1, step=1, key=f"count_{n}")
    for i in range(int(count)):
        c1, c2, c3 = st.columns([2, 1, 3])
        item_name = c1.text_input(f"Item {i + 1} name", key=f"iname_{n}_{i}")
        item_amt = c2.number_input("Amount", min_value=0.0, step=0.01,
                                   format="%.2f", key=f"iamt_{n}_{i}")
        item_who = c3.multiselect("Shared by", list(names), format_func=names.get,
                                  key=f"iwho_{n}_{i}")
        items_data.append((item_name.strip() or f"Item {i + 1}",
                           to_minor(item_amt), item_who))
else:
    amount = st.number_input(f"Amount ({currency})", min_value=0.0, step=0.01,
                             format="%.2f", key=f"amount_{n}")
    total = to_minor(amount)
    participants = st.multiselect(
        "Split between", list(names), default=list(names),
        format_func=names.get, key=f"participants_{n}",
    )
    if method == "custom":
        for pid in participants:
            shares_in[pid] = to_minor(st.number_input(
                f"{names[pid]}'s share", min_value=0.0, step=0.01,
                format="%.2f", key=f"cust_{n}_{pid}"))
        st.caption(f"Entered {format_money(sum(shares_in.values()), currency)} "
                   f"of {format_money(total, currency)}")
    elif method == "percentage":
        for pid in participants:
            percents[pid] = st.number_input(
                f"{names[pid]} (%)", min_value=0.0, max_value=100.0, step=0.01,
                format="%.2f", key=f"pct_{n}_{pid}")
        st.caption(f"Total: {sum(percents.values()):.2f}% (must be exactly 100)")

# ---------------------------------------------------------------------------
# Part 3: calculate the shares with the logic functions
# ---------------------------------------------------------------------------
try:
    if method == "item":
        total, shares = item_split([(a, who) for _, a, who in items_data])
    elif total <= 0:
        split_error = "Enter an amount greater than zero."
    elif not participants:
        split_error = "Choose at least one person to split between."
    elif method == "equal":
        shares = equal_split(total, participants)
    elif method == "custom":
        shares = custom_split(total, shares_in)
    else:
        shares = percentage_split(total, {p: str(v) for p, v in percents.items()})
except ValidationError as error:
    split_error = str(error)

# ---------------------------------------------------------------------------
# Part 4: who paid (one or several)
# ---------------------------------------------------------------------------
st.divider()
payer_ids = st.multiselect(
    "Paid by", list(names), default=[list(names)[0]],
    format_func=names.get, key=f"payers_{n}",
)
payers = {}
if len(payer_ids) == 1:
    payers = {payer_ids[0]: total}  # the one payer paid everything
else:
    for pid in payer_ids:
        payers[pid] = to_minor(st.number_input(
            f"{names[pid]} paid", min_value=0.0, step=0.01,
            format="%.2f", key=f"paid_{n}_{pid}"))
    if payers:
        st.caption(f"Paid {format_money(sum(payers.values()), currency)} "
                   f"of {format_money(total, currency)}")

payer_error = None
if shares is not None:
    if not payer_ids:
        payer_error = "Choose who paid."
    else:
        try:
            validate_payers(total, payers)
        except ValidationError as error:
            payer_error = str(error)
ready = shares is not None and payer_error is None and rate_error is None

# ---------------------------------------------------------------------------
# Part 5: preview and Save
# ---------------------------------------------------------------------------
st.divider()
st.subheader("Preview")

if split_error:
    st.info(split_error)
elif payer_error:
    st.warning(payer_error)
if rate_error and shares is not None:
    st.warning(rate_error)

if shares:
    st.markdown(f"**Expense:** {title.strip() or '(no title yet)'}")
    st.markdown(f"**Total:** {format_money(total, currency)}")
    if needs_conversion(currency, base) and rate_error is None:
        st.markdown(f"**In {base}:** about {format_money(convert(total, rate_text), base)} "
                    f"(rate {rate_text.strip()})")
    st.markdown("**Paid by:**")
    for pid, paid in payers.items():
        st.write(f"- {names[pid]}: {format_money(paid, currency)}")
    st.markdown("**Share:**")
    for pid, share in shares.items():
        st.write(f"- {names[pid]}: {format_money(share, currency)}")

if st.button("Save expense", type="primary", disabled=not ready, key=f"save_{n}"):
    try:
        with db_session() as conn:
            saved = es.add_expense(
                conn, group.id, title, category, expense_date,
                payers=payers,
                split_method=method,
                total=None if method == "item" else total,
                member_ids=participants,
                shares=shares_in,
                percentages={p: str(v) for p, v in percents.items()},
                items=items_data,
                currency=currency,
                rate=rate_text,
            )
        flash(f"Expense '{saved.title}' saved.")
        st.session_state["expense_form_n"] = n + 1  # new keys = empty form
        st.rerun()
    except ValidationError as error:
        st.error(str(error))