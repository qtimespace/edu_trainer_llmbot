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


def test_hidden_tab_stays_online_though_the_browser_throttles_its_pings(engine):
    """Скрытую вкладку Chrome будит раз в минуту — «вкладка скрыта», а не «не в сети»."""
    kid, store = _kid(engine), PresenceStore(engine)
    now = datetime.now(UTC)
    store.ping(kid.id, now, state="hidden")
    assert store.online([kid.id], now + timedelta(seconds=100)) == {kid.id}
    assert store.online([kid.id], now + timedelta(seconds=200)) == set()


def test_attention_changes_are_logged_and_summed(engine):
    kid, store = _kid(engine), PresenceStore(engine)
    t0 = datetime.now(UTC).replace(microsecond=0)
    store.ping(kid.id, t0, state="focused")
    store.ping(kid.id, t0 + timedelta(seconds=15), state="focused")  # то же состояние — в ленту не пишем
    store.ping(kid.id, t0 + timedelta(seconds=30), state="focused")
    store.ping(kid.id, t0 + timedelta(seconds=45), state="focused")
    store.ping(kid.id, t0 + timedelta(seconds=60), state="hidden")
    store.ping(kid.id, t0 + timedelta(seconds=110), state="hidden")  # скрытую вкладку браузер будит реже
    store.ping(kid.id, t0 + timedelta(seconds=120), state="blurred")
    a = store.attention(kid.id, since=t0 - timedelta(hours=1), now=t0 + timedelta(seconds=150))
    assert a["state"] == "blurred" and a["since"] == (t0 + timedelta(seconds=120)).isoformat()
    assert [e["state"] for e in a["events"]] == ["focused", "hidden", "blurred"]
    assert a["totals"] == {"focused": 60, "hidden": 60, "blurred": 30}


def test_time_offline_is_not_counted_as_focused(engine):
    """Закрыл вкладку и вернулся через полчаса: перерыв — «не в сети», а не «смотрел»."""
    kid, store = _kid(engine), PresenceStore(engine)
    t0 = datetime.now(UTC).replace(microsecond=0)
    store.ping(kid.id, t0, state="focused")
    store.ping(kid.id, t0 + timedelta(seconds=30), state="focused")
    store.ping(kid.id, t0 + timedelta(minutes=30), state="focused")
    a = store.attention(kid.id, since=t0, now=t0 + timedelta(minutes=30, seconds=10))
    assert [e["state"] for e in a["events"]] == ["focused", "offline", "focused"]
    assert a["totals"]["focused"] == 40


def test_offline_student_has_no_current_state(engine):
    kid, store = _kid(engine), PresenceStore(engine)
    t0 = datetime.now(UTC)
    store.ping(kid.id, t0, state="focused")
    assert store.attention(kid.id, since=t0, now=t0 + timedelta(minutes=5))["state"] == "offline"


def test_teacher_sees_attention_student_cannot(api):
    from trainer.classroom.groups import GroupStore
    AccountStore(api).create_account("anna", PASS, role="teacher")
    groups = GroupStore(api)
    groups.create("g", 2)
    account, _ = groups.add_student("kid1", "kid1")
    AccountStore(api).set_password(account.id, PASS)
    kid = TestClient(app)
    login(kid, "kid1")
    assert kid.post("/presence/ping", json={"state": "hidden"}).status_code == 204
    assert kid.post("/presence/ping", json={"state": "playing"}).status_code == 422
    teacher = TestClient(app)
    login(teacher, "anna")
    got = teacher.get(f"/group/students/{account.id}/attention").json()
    assert got["state"] == "hidden" and got["events"][-1]["state"] == "hidden"
    room = next(r for r in teacher.get("/office").json()["rooms"] if r["student"])
    assert room["attention"]["state"] == "hidden"
    assert kid.get(f"/group/students/{account.id}/attention").status_code == 403


def test_ping_api_and_logout_makes_offline(api):
    kid = _kid(api)
    c = TestClient(app)
    login(c, "kid")
    assert c.post("/presence/ping").status_code == 204
    assert PresenceStore(api).online([kid.id]) == {kid.id}
    c.post("/auth/logout")
    assert PresenceStore(api).online([kid.id]) == set()
