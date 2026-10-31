import pytest

from tests.helpers import PASS
from trainer.accounts.store import AccountStore
from trainer.classroom.groups import GroupStore
from trainer.curriculum.tasks import Check
from trainer.sandbox.backend import ExecResult, FakeBackend
from trainer.sandbox.checks import recent_history, run_checks
from trainer.sandbox.manager import SandboxManager


@pytest.fixture
def kid(engine):
    groups = GroupStore(engine)
    groups.create("g", 2)
    account, _ = groups.add_student("kid1", "kid1")
    AccountStore(engine).set_password(account.id, PASS)
    return engine, account.id


def test_pass_and_fail(kid):
    engine, sid = kid
    fake = FakeBackend(lambda name, cmd, user: ExecResult(0 if "a.txt" in cmd[-1] else 1, "out" * 300))
    results = run_checks(SandboxManager(fake, engine), sid, [Check(cmd="test -f ~/a.txt", about="a"),
                                                              Check(cmd="test -d ~/Temp", about="Temp")])
    assert [r.passed for r in results] == [True, False]
    assert len(results[0].output) <= 500 and results[1].about == "Temp"
    name, cmd, user = fake.calls[0]
    # проверка не читает настройки оболочки ученика (alias test=true не обманет) и идёт в чистом окружении
    assert cmd[:2] == ["env", "-i"] and cmd[-4:] == ["--noprofile", "--norc", "-c", "test -f ~/a.txt"]
    assert "HOME=/home/student" in cmd and user == "student"


def test_check_timeout(kid):
    engine, sid = kid
    fake = FakeBackend(lambda name, cmd, user: ExecResult(124, ""))  # timeout(1) завершает с кодом 124
    [r] = run_checks(SandboxManager(fake, engine), sid, [Check(cmd="while true; do :; done", about="цикл")])
    assert not r.passed and "10 с" in r.output


def test_check_backend_error_is_failed_check(kid):
    engine, sid = kid

    def boom(name, cmd, user):
        raise RuntimeError("docker down")
    [r] = run_checks(SandboxManager(FakeBackend(boom), engine), sid, [Check(cmd="true", about="x")])
    assert not r.passed and "не удалось" in r.output


def test_history_merges_lobby_and_student(kid):
    engine, sid = kid
    files = {"/home/lobby/.bash_history": "#1700000000\nssh student@lab\n#1700000300\nexit\n",
             "/home/student/.bash_history": "#1700000100\nls\n#1700000200\nmkdir Temp\n"}

    def handler(name, cmd, user):
        assert cmd[:3] == ["tail", "-c", "65536"]  # огромную историю целиком не читаем
        return ExecResult(0, files.get(cmd[-1], ""))
    lines = recent_history(SandboxManager(FakeBackend(handler), engine), sid, limit=3)
    assert lines == ["student$ ls", "student$ mkdir Temp", "lobby$ exit"]
