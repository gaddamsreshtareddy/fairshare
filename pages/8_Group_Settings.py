"""FairShare: Group Settings page (manage the open group and its members)."""

import streamlit as st

from logic.validators import (
    SUPPORTED_CURRENCIES,
    ValidationError,
    clean_text,
)

from services import group_service as svc

from ui.components import (
    db_session,
    flash,
    render_sidebar,
    require_open_group,
    show_flash,
)

st.set_page_config(page_title="Group Settings - FairShare", page_icon="💸", layout="wide")
render_sidebar()

st.title("⚙️ Group Settings")
group = require_open_group()  # stops the page here if no group is open
show_flash()

with db_session() as conn:
    summary = svc.get_group_summary(conn, group.id)
    members = svc.list_members(conn, group.id)

# ---------------------------------------------------------------------------
# Group summary
# ---------------------------------------------------------------------------
st.subheader(summary.group.name)
col1, col2, col3 = st.columns(3)
col1.metric("Base currency", summary.group.base_currency)
col2.metric("Active members", summary.active_member_count)
col3.metric("Inactive members", summary.inactive_member_count)

if summary.currency_locked:
    st.caption("🔒 The base currency is locked because this group already has expenses.")
# ---------------------------------------------------------------------------
# Edit group
# ---------------------------------------------------------------------------
st.divider()
st.subheader("Edit group")

with st.form("edit_group_form"):
    name_value = st.text_input(
        "Group name",
        value=summary.group.name,
    )

    currency_value = st.selectbox(
        "Base currency",
        options=SUPPORTED_CURRENCIES,
        index=SUPPORTED_CURRENCIES.index(summary.group.base_currency),
        disabled=summary.currency_locked,
    )

    save_clicked = st.form_submit_button(
        "Save changes",
        type="primary",
    )

if save_clicked:
    try:
        with db_session() as conn:
            updated = svc.update_group(
                conn,
                group.id,
                name_value,
                currency_value,
            )

        flash(f"Group '{updated.name}' updated successfully.")
        st.rerun()

    except ValidationError as error:
        st.error(str(error))
# ---------------------------------------------------------------------------
# Add member
# ---------------------------------------------------------------------------
st.divider()
st.subheader("Add member")

with st.form("add_member_form", clear_on_submit=True):
    new_name = st.text_input(
        "Member name",
        placeholder="e.g. Ravi"
    )
    add_clicked = st.form_submit_button(
        "Add member",
        type="primary"
    )

if add_clicked:
    wanted = clean_text(new_name).casefold()
    returning = any(
        m.name.casefold() == wanted and not m.is_active
        for m in members
    )

    try:
        with db_session() as conn:
            member = svc.add_member(
                conn,
                group.id,
                new_name
            )

        if returning:
            flash(
                f"'{member.name}' was inactive and has been reactivated."
            )
        else:
            flash(
                f"'{member.name}' added to the group."
            )

        st.rerun()

    except ValidationError as error:
        st.error(str(error))
# ---------------------------------------------------------------------------
# Member list (read-only for now)
# ---------------------------------------------------------------------------
# Member list and management
# ---------------------------------------------------------------------------
st.divider()
st.subheader("Members")

if not members:
    st.info("No members yet. Add the first one above.")
else:
    st.dataframe(
        [
            {"Name": m.name, "Status": "Active" if m.is_active else "Inactive"}
            for m in members
        ],
        hide_index=True,
        use_container_width=True,
    )

    st.markdown("#### Manage a member")
    by_id = {m.id: m for m in members}

    def member_label(member_id):
        member = by_id[member_id]
        return member.name if member.is_active else f"{member.name} (inactive)"

    chosen_id = st.selectbox("Choose a member", list(by_id), format_func=member_label)
    chosen = by_id[chosen_id]

    rename_col, status_col, remove_col = st.columns(3, gap="large")

    with rename_col:
        with st.form(f"rename_form_{chosen.id}"):
            renamed = st.text_input("New name", value=chosen.name)
            rename_clicked = st.form_submit_button("Rename")

    with status_col:
        st.write("Status")
        if chosen.is_active:
            toggle_clicked = st.button(
                "Deactivate", key=f"deactivate_{chosen.id}",
                help="Hide from new expenses. History is kept.",
            )
        else:
            toggle_clicked = st.button(
                "Reactivate", key=f"reactivate_{chosen.id}",
                help="Bring this member back.",
            )

    with remove_col:
        with st.form(f"remove_form_{chosen.id}"):
            confirmed = st.checkbox("Yes, remove this member")
            remove_clicked = st.form_submit_button("Remove member")

    st.caption(
        "Remove deletes a member who has never been used. A member who appears "
        "in expenses or settlements is deactivated instead, so history stays correct."
    )

    # --- Handle whichever button was clicked ---------------------------------
    try:
        if rename_clicked:
            if clean_text(renamed) == chosen.name:
                st.info("That is already this member's name.")
            else:
                with db_session() as conn:
                    updated = svc.rename_member(conn, chosen.id, renamed)
                flash(f"'{chosen.name}' renamed to '{updated.name}'.")
                st.rerun()

        elif toggle_clicked:
            with db_session() as conn:
                if chosen.is_active:
                    svc.deactivate_member(conn, chosen.id)
                    flash(f"'{chosen.name}' deactivated.")
                else:
                    svc.reactivate_member(conn, chosen.id)
                    flash(f"'{chosen.name}' reactivated.")
            st.rerun()

        elif remove_clicked:
            if not confirmed:
                st.warning("Tick the box first to confirm the removal.")
            else:
                with db_session() as conn:
                    outcome = svc.remove_member(conn, chosen.id)
                if outcome == "deleted":
                    flash(f"'{chosen.name}' was removed from the group.")
                else:
                    flash(
                        f"'{chosen.name}' appears in expenses or settlements, so they "
                        "were deactivated instead of deleted. Their history is kept."
                    )
                st.rerun()

    except ValidationError as error:
        st.error(str(error))