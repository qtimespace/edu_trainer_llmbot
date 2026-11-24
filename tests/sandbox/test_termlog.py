"""Экран терминала ученика для преподавателя: вывод (с эхом ввода) пишется по пути через API и проигрывается в панели."""
import base64
import time

from fastapi.testclient import TestClient

from apps.api.main import app
from tests.helpers import login
from tests.sandbox.test_terminal_ws import ORIGIN, _kid, world  # noqa: F401 — фикстура
from trainer.accounts.store import AccountStore
from trainer.sandbox.termlog import TerminalLog


def _kid_id(engine) -> str:
    return AccountStore(engine).by_login("kid1").id


def test_log_keeps_order_reads_after_id_and_prunes_old_output(api, world):
    log, kid = TerminalLog(api, keep_bytes=10), _kid_id(api)
    log.size(kid, 120, 30)
    for chunk in (b"aaaa", b"bbbb", b"cccc", b"dddd"):
        log.append(kid, chunk)
    rows = log.since(kid)
    # хранится не больше keep_bytes вывода (целыми кусками, свежие); размер окна — всегда последний перед ними
    assert [(r.kind, r.data) for r in rows] == [("size", b"120x30"), ("out", b"bbbb"), ("out", b"cccc"), ("out", b"dddd")]
    assert [r.data for r in log.since(kid, after=rows[2].id)] == [b"dddd"]
    assert log.since(_kid_id(api), after=rows[-1].id) == []


def test_terminal_output_and_window_size_are_recorded(api, world):
    with _kid().websocket_connect("/ws/terminal", headers=ORIGIN) as ws:
        ws.send_text('{"type": "resize", "cols": 100, "rows": 30}')
        ws.send_bytes(b"echo hi\r\nhi\r\n")
        assert ws.receive_bytes() == b"echo hi\r\nhi\r\n"
    deadline = time.time() + 3
    while time.time() < deadline and not any(r.kind == "out" for r in TerminalLog(api).since(_kid_id(api))):
        time.sleep(0.05)
    rows = TerminalLog(api).since(_kid_id(api))
    assert b"".join(r.data for r in rows if r.kind == "out") == b"echo hi\r\nhi\r\n"
    assert ("size", b"100x30") in [(r.kind, r.data) for r in rows]


def test_teacher_reads_the_screen_student_cannot(api, world):
    kid = _kid_id(api)
    TerminalLog(api).size(kid, 90, 20)
    TerminalLog(api).append(kid, "ls\r\nsite-maket\r\n".encode())
    teacher = TestClient(app)
    login(teacher, "anna")
    got = teacher.get(f"/group/students/{kid}/terminal").json()
    assert got["chunks"][0] == {"id": got["chunks"][0]["id"], "kind": "size", "data": base64.b64encode(b"90x20").decode()}
    assert base64.b64decode(got["chunks"][1]["data"]) == b"ls\r\nsite-maket\r\n"
    assert got["last"] == got["chunks"][-1]["id"]
    assert teacher.get(f"/group/students/{kid}/terminal", params={"after": got["last"]}).json() == {
        "chunks": [], "last": got["last"]}
    assert _kid().get(f"/group/students/{kid}/terminal").status_code == 403
