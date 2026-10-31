import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from tests.conftest import TABLES


def test_migration_creates_tables(engine):
    with engine.connect() as c:
        names = {r[0] for r in c.execute(text(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"))}
    assert set(TABLES) <= names


@pytest.mark.parametrize("size,ok", [(1, False), (2, True), (5, True), (6, False)])
def test_group_size_bounds(engine, size, ok):
    stmt = text("INSERT INTO groups (name, size) VALUES ('g', :s)")
    if ok:
        with engine.begin() as c:
            c.execute(stmt, {"s": size})
    else:
        with pytest.raises(IntegrityError), engine.begin() as c:
            c.execute(stmt, {"s": size})
