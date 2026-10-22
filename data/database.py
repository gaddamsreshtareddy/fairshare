"""Database connection helper for FairShare.

This is the only file that knows where the database file lives and how
to open it. Every other part of the app asks this file for a connection.
"""

import sqlite3
from pathlib import Path

# Project root = the folder that contains app.py (two levels up from this file).
BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "storage" / "fairshare.db"


def get_connection(db_path=None) -> sqlite3.Connection:
    """Open a connection to the SQLite database.

    db_path is optional. Normally we use the default file in storage/.
    Tests pass a temporary path so they never touch real data.
    """
    path = Path(db_path) if db_path else DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)  # make sure the folder exists

    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row            # lets us read columns by name
    conn.execute("PRAGMA foreign_keys = ON")  # make SQLite enforce table links
    return conn




# ---------------------------------------------------------------------------
# Schema: the definition of every table.
# Money columns are INTEGERS holding minor units (paise/cents). 25075 = 250.75
# ---------------------------------------------------------------------------
SCHEMA = """
CREATE TABLE IF NOT EXISTS groups (
    id            INTEGER PRIMARY KEY,
    name          TEXT NOT NULL CHECK (length(trim(name)) > 0),
    base_currency TEXT NOT NULL DEFAULT 'INR' CHECK (length(base_currency) = 3),
    created_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS members (
    id         INTEGER PRIMARY KEY,
    group_id   INTEGER NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
    name       TEXT NOT NULL COLLATE NOCASE CHECK (length(trim(name)) > 0),
    is_active  INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (group_id, name)
);

CREATE TABLE IF NOT EXISTS expenses (
    id              INTEGER PRIMARY KEY,
    group_id        INTEGER NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
    title           TEXT NOT NULL CHECK (length(trim(title)) > 0),
    category        TEXT NOT NULL DEFAULT 'Other'
                    CHECK (category IN ('Food','Hotel','Transport',
                                        'Entertainment','Shopping','Other')),
    expense_date    TEXT NOT NULL,
    currency        TEXT NOT NULL CHECK (length(currency) = 3),
    original_amount INTEGER NOT NULL CHECK (original_amount > 0),
    exchange_rate   REAL NOT NULL DEFAULT 1.0 CHECK (exchange_rate > 0),
    base_amount     INTEGER NOT NULL CHECK (base_amount > 0),
    split_method    TEXT NOT NULL
                    CHECK (split_method IN ('equal','custom','percentage','item')),
    created_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS expense_payers (
    id          INTEGER PRIMARY KEY,
    expense_id  INTEGER NOT NULL REFERENCES expenses(id) ON DELETE CASCADE,
    member_id   INTEGER NOT NULL REFERENCES members(id),
    amount_paid INTEGER NOT NULL CHECK (amount_paid > 0),
    UNIQUE (expense_id, member_id)
);

CREATE TABLE IF NOT EXISTS expense_splits (
    id           INTEGER PRIMARY KEY,
    expense_id   INTEGER NOT NULL REFERENCES expenses(id) ON DELETE CASCADE,
    member_id    INTEGER NOT NULL REFERENCES members(id),
    share_amount INTEGER NOT NULL CHECK (share_amount >= 0),
    percentage   REAL CHECK (percentage IS NULL OR (percentage >= 0 AND percentage <= 100)),
    UNIQUE (expense_id, member_id)
);

CREATE TABLE IF NOT EXISTS items (
    id         INTEGER PRIMARY KEY,
    expense_id INTEGER NOT NULL REFERENCES expenses(id) ON DELETE CASCADE,
    name       TEXT NOT NULL CHECK (length(trim(name)) > 0),
    amount     INTEGER NOT NULL CHECK (amount > 0)
);

CREATE TABLE IF NOT EXISTS item_consumers (
    item_id   INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    member_id INTEGER NOT NULL REFERENCES members(id),
    PRIMARY KEY (item_id, member_id)
);

CREATE TABLE IF NOT EXISTS settlements (
    id             INTEGER PRIMARY KEY,
    group_id       INTEGER NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
    from_member_id INTEGER NOT NULL REFERENCES members(id),
    to_member_id   INTEGER NOT NULL REFERENCES members(id),
    amount         INTEGER NOT NULL CHECK (amount > 0),
    status         TEXT NOT NULL DEFAULT 'Pending'
                   CHECK (status IN ('Pending','Completed')),
    created_at     TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at   TEXT,
    CHECK (from_member_id <> to_member_id)
);

CREATE TABLE IF NOT EXISTS settlement_history (
    id             INTEGER PRIMARY KEY,
    group_id       INTEGER NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
    settlement_id  INTEGER REFERENCES settlements(id) ON DELETE SET NULL,
    from_member_id INTEGER NOT NULL REFERENCES members(id),
    to_member_id   INTEGER NOT NULL REFERENCES members(id),
    amount         INTEGER NOT NULL CHECK (amount > 0),
    event          TEXT NOT NULL CHECK (event IN ('Generated','Completed','Reopened')),
    event_at       TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_members_group     ON members(group_id);
CREATE INDEX IF NOT EXISTS idx_expenses_group    ON expenses(group_id);
CREATE INDEX IF NOT EXISTS idx_payers_expense    ON expense_payers(expense_id);
CREATE INDEX IF NOT EXISTS idx_splits_expense    ON expense_splits(expense_id);
CREATE INDEX IF NOT EXISTS idx_settlements_group ON settlements(group_id);
"""


def init_db(db_path=None) -> None:
    """Create all tables if they don't exist yet. Safe to call repeatedly."""
    conn = get_connection(db_path)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()
        