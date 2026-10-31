from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from apps.api.main import app
from tests.helpers import PASS, login
from trainer.accounts.store import AccountStore
from trainer.classroom.presence import PresenceStore


def _kid(engine):
    return AccountStore(engine).create_account("kid", PASS, role="student")


def test_online_within_window(engine):
    kid, store = _kid(engine), PresenceStore(engine)
    now = datetime.now(UTC)
    store.ping(kid.id, now)
    assert store.online([kid.id], now + timedelta(seconds=39)) == {kid.id}


def test_offline_after_41s(engine):
    kid, store = _kid(engine), PresenceStore(engine)
    now = datetime.now(UTC)
    store.ping(kid.id, now)
    assert store.online([kid.id], now + timedelta(seconds=41)) == set()
    assert store.online([], now) == set()


def test_ping_api_and_logout_makes_offline(api):
    kid = _kid(api)
    c = TestClient(app)
    login(c, "kid")
    assert c.post("/presence/ping").status_code == 204
    assert PresenceStore(api).online([kid.id]) == {kid.id}
    c.post("/auth/logout")
    assert PresenceStore(api).online([kid.id]) == set()
