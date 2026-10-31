"""Reusable UI helpers shared by every Streamlit page (presentation layer)."""

from contextlib import contextmanager

import streamlit as st

from data.database import get_connection, init_db
from logic.validators import ValidationError
from services import group_service as svc


# ---------------------------------------------------------------------------
# Database access
# ---------------------------------------------------------------------------
@st.cache_resource
def _init_database_once() -> bool:
    """Create the tables the first time the app runs (cached afterwards)."""
    init_db()
    return True


@contextmanager
def db_session():
    """Open a database connection for one block of work, then always close it.

    Usage:
        with db_session() as conn:
            groups = svc.list_groups(conn)
    """
    _init_database_once()
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# "Which group is open?" memory
# ---------------------------------------------------------------------------
def get_current_group_id() -> int | None:
    return st.session_state.get("group_id")


def set_current_group(group_id: int | None) -> None:
    st.session_state["group_id"] = group_id


# ---------------------------------------------------------------------------
# Flash messages (shown once, on the next run)
# ---------------------------------------------------------------------------
def flash(message: str) -> None:
    st.session_state["flash"] = message


def show_flash() -> None:
    message = st.session_state.pop("flash", None)
    if message:
        st.success(message)


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
def render_sidebar() -> None:
    """Show the currently open group in the sidebar."""
    with st.sidebar:
        st.divider()
        group_id = get_current_group_id()
        if group_id is None:
            st.caption("No group open. Go to Home to create or open one.")
            return
        try:
            with db_session() as conn:
                group = svc.get_group(conn, group_id)
        except ValidationError:
            set_current_group(None)  # the group no longer exists
            st.caption("No group open. Go to Home to create or open one.")
            return
        st.caption("CURRENT GROUP")
        st.markdown(f"**{group.name}** ({group.base_currency})")


# ---------------------------------------------------------------------------
# Guard for pages that need an open group
# ---------------------------------------------------------------------------
def require_open_group():
    """Return the currently open Group, or show a message and stop the page.

    Call this near the top of any page that only makes sense when a group is
    open. If no group is open, the rest of the page is not run.
    """
    group_id = get_current_group_id()
    if group_id is not None:
        try:
            with db_session() as conn:
                return svc.get_group(conn, group_id)
        except ValidationError:
            set_current_group(None)  # the remembered group no longer exists

    st.info("No group is open. Go to the Home page to create or open a group.")
    st.page_link("home.py", label="Go to Home", icon="🏠")
    st.stop()  # nothing below this line runs