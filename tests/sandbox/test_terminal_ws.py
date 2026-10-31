import json
import time

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from apps.api.main import app
from tests.helpers import PASS, login
from trainer.accounts.store import AccountStore
from trainer.classroom.groups import GroupStore
from trainer.sandbox.backend import FakeBackend

ORIGIN = {"origin": "http://localhost:3000"}


@pytest.fixture
def world(api):
    import apps.api.sandbox as sandbox_api
    fake = FakeBackend()
    sandbox_api.BACKENDS["fake"] = fake
    AccountStore(api).create_account("anna", PASS, role="teacher")
    groups = GroupStore(api)
    groups.create("g", 2)
    account, _ = groups.add_student("kid1", "kid1")
    AccountStore(api).set_password(account.id, PASS)
    return fake


def _kid():
    c = TestClient(app)
    login(c, "kid1")
    return c


def test_ws_echo_roundtrip(world):
    with _kid().websocket_connect("/ws/terminal", headers=ORIGIN) as ws:
        ws.send_bytes(b"ls -la\n")
        assert ws.receive_bytes() == b"ls -la\n"
    deadline = time.time() + 2
    while not world.ttys[0].closed and time.time() < deadline:
        time.sleep(0.02)
    assert world.ttys[0].closed  # закрыли вкладку — оболочка закрыта


def test_resize_forwarded(world):
    with _kid().websocket_connect("/ws/terminal", headers=ORIGIN) as ws:
        ws.send_text(json.dumps({"type": "resize", "cols": 120, "rows": 40}))
        ws.send_bytes(b"x")
        ws.receive_bytes()
    assert world.ttys[0].size == (120, 40)


def test_bad_resize_is_ignored_and_clamped(world):
    with _kid().websocket_connect("/ws/terminal", headers=ORIGIN) as ws:
        ws.send_text(json.dumps({"type": "resize", "cols": "abc", "rows": None}))
        ws.send_text(json.dumps({"type": "resize", "cols": 100000, "rows": -5}))
        ws.send_bytes(b"x")
        assert ws.receive_bytes() == b"x"  # соединение живо
    assert world.ttys[0].size == (500, 1)


def test_must_change_password_blocks_terminal(world, api):
    kid = _kid()
    account = AccountStore(api).by_login("kid1")
    AccountStore(api).set_password(account.id, PASS, must_change=True)
    with pytest.raises(WebSocketDisconnect) as e, kid.websocket_connect("/ws/terminal", headers=ORIGIN) as ws:
        ws.receive_bytes()
    assert e.value.code == 4403


@pytest.mark.parametrize("who,headers", [("anon", ORIGIN), ("teacher", ORIGIN), ("kid", {"origin": "https://evil.example"}),
                                         ("kid", {})])
def test_ws_rejects_foreign_or_anonymous(world, who, headers):
    c = TestClient(app)
    if who == "teacher":
        login(c, "anna")
    elif who == "kid":
        login(c, "kid1")
    with pytest.raises(WebSocketDisconnect) as e, c.websocket_connect("/ws/terminal", headers=headers) as ws:
        ws.receive_bytes()
    assert e.value.code in (4401, 4403)
    assert world.ttys == []
