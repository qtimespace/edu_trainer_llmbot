"""Тесты на настоящем Docker (запуск на сервере: pytest -m docker). Нужен образ trainer-sandbox:1."""
import time
import uuid

import pytest

from trainer.sandbox.docker_backend import DockerBackend
from trainer.settings import Settings

pytestmark = pytest.mark.docker


@pytest.fixture
def box():
    backend = DockerBackend(Settings(_env_file=None))
    name, volume = f"trainer-sbx-test-{uuid.uuid4().hex[:6]}", f"trainer-home-test-{uuid.uuid4().hex[:6]}"
    backend.ensure(name, {"LESSON_PASSWORD": "kot-les-dom"}, volume)
    time.sleep(1)  # sshd стартует
    yield backend, name
    backend.remove(name, volume, wipe=True)


def test_ssh_into_lab_with_lesson_password(box):
    backend, name = box
    r = backend.exec(name, ["bash", "-lc", "sshpass -p kot-les-dom ssh -o StrictHostKeyChecking=no student@lab whoami"],
                     user="lobby", timeout_s=20)
    assert r.exit_code == 0 and "student" in r.output


def test_pids_limit_holds(box):
    backend, name = box
    backend.exec(name, ["bash", "-c", "timeout 5 bash -c ':(){ :|:& };:' || true"], user="student", timeout_s=15)
    assert backend.exec(name, ["echo", "ok"], user="student", timeout_s=10).output.strip() == "ok"


def test_history_written_immediately(box):
    backend, name = box
    tty = backend.attach_tty(name, "student")
    tty.write(b"echo hello-history\n")
    time.sleep(1)
    tty.close()
    r = backend.exec(name, ["cat", "/home/student/.bash_history"], user="student", timeout_s=10)
    assert "echo hello-history" in r.output


def test_no_icc():
    backend = DockerBackend(Settings(_env_file=None))
    a, b = f"trainer-sbx-icc-a-{uuid.uuid4().hex[:4]}", f"trainer-sbx-icc-b-{uuid.uuid4().hex[:4]}"
    try:
        backend.ensure(a, {"LESSON_PASSWORD": "x-y-z"}, a + "-v")
        backend.ensure(b, {"LESSON_PASSWORD": "x-y-z"}, b + "-v")
        ip_b = backend.exec(b, ["hostname", "-i"], user="student", timeout_s=10).output.split()[0]
        r = backend.exec(a, ["bash", "-c", f"timeout 3 bash -c '</dev/tcp/{ip_b}/22'"], user="student", timeout_s=10)
        assert r.exit_code != 0
    finally:
        backend.remove(a, a + "-v", wipe=True)
        backend.remove(b, b + "-v", wipe=True)


def test_no_host_access(box):
    """После infra/deploy/sandbox-firewall.sh: шлюз сети (хост) и частные сети недоступны, интернет — доступен."""
    backend, name = box
    gw = backend.exec(name, ["sh", "-c", "ip route 2>/dev/null | awk '/default/{print $3}' || "
                                         "awk '$2==\"00000000\"{print $3}' /proc/net/route"], user="root",
                      timeout_s=5).output.strip()
    r = backend.exec(name, ["bash", "-c", f"timeout 3 bash -c '</dev/tcp/{gw or '172.17.0.1'}/22'"], user="student",
                     timeout_s=10)
    assert r.exit_code != 0
    web = backend.exec(name, ["curl", "-sS", "-o", "/dev/null", "-w", "%{http_code}", "https://github.com"],
                       user="student", timeout_s=15)
    assert web.output.strip().startswith(("2", "3"))
