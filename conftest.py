"""Shared pytest setup. Fixtures defined here are available in every test file."""

import pytest

from data.database import get_connection, init_db


@pytest.fixture
def conn(tmp_path):
    """A fresh, empty FairShare database for one test (never the real one)."""
    db_file = tmp_path / "test.db"
    init_db(db_file)
    connection = get_connection(db_file)
    yield connection
    connection.close()