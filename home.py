"""FairShare: Home / Welcome page (Streamlit entry point)."""

import streamlit as st

from logic.validators import SUPPORTED_CURRENCIES, ValidationError
from services import group_service as svc
from ui.components import (
    db_session,
    flash,
    get_current_group_id,
    render_sidebar,
    set_current_group,
    show_flash,
)

st.set_page_config(page_title="FairShare", page_icon="💸", layout="wide")
render_sidebar()

st.title("💸 FairShare")
st.caption("Intelligent Group Expense Sharing and Minimum Transaction Settlement System")
show_flash()

left, right = st.columns(2, gap="large")

# ---------------------------------------------------------------------------
# Create New Group
# ---------------------------------------------------------------------------
with left:
    st.subheader("Create New Group")
    with st.form("create_group_form", clear_on_submit=True):
        name = st.text_input("Group name", placeholder="e.g. Goa Trip 2025")
        currency = st.selectbox("Base currency", SUPPORTED_CURRENCIES)
        submitted = st.form_submit_button("Create group", type="primary")

    if submitted:
        try:
            with db_session() as conn:
                group = svc.create_group(conn, name, currency)
            set_current_group(group.id)
            flash(f"Group '{group.name}' created. Add its members in Group Settings.")
            st.rerun()
        except ValidationError as error:
            st.error(str(error))

# ---------------------------------------------------------------------------
# Open Existing Group
# ---------------------------------------------------------------------------
with right:
    st.subheader("Open Existing Group")
    with db_session() as conn:
        groups = svc.list_groups(conn)

    if not groups:
        st.info("No groups yet. Create your first group on the left.")
    else:
        labels = {g.id: f"{g.name} ({g.base_currency})" for g in groups}
        group_ids = list(labels)
        current_id = get_current_group_id()
        start_index = group_ids.index(current_id) if current_id in group_ids else 0

        chosen_id = st.selectbox(
            "Choose a group", group_ids, index=start_index, format_func=labels.get
        )
        if st.button("Open group"):
            set_current_group(chosen_id)
            flash(f"Opened '{labels[chosen_id]}'.")
            st.rerun()

# ---------------------------------------------------------------------------
# Current group summary
# ---------------------------------------------------------------------------
current_id = get_current_group_id()
if current_id is not None:
    try:
        with db_session() as conn:
            summary = svc.get_group_summary(conn, current_id)
    except ValidationError:
        set_current_group(None)
        st.rerun()

    st.divider()
    st.subheader(f"Current group: {summary.group.name}")
    col1, col2, col3 = st.columns(3)
    col1.metric("Base currency", summary.group.base_currency)
    col2.metric("Active members", summary.active_member_count)
    col3.metric("Inactive members", summary.inactive_member_count)