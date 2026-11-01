"""Тесты на настоящем Docker (запуск на сервере: pytest -m docker). Нужен образ trainer-sandbox:1."""
import time
import uuid

import pytest

from trainer.sandbox.docker_backend import DockerBackend
from trainer.settings import Settings

pytestmark = pytest.mark.docker


@pytest.fixture
def box():
    backend = DockerBackend(Settings(_env_file=None, sandbox_disk_quota=False))
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
    backend = DockerBackend(Settings(_env_file=None, sandbox_disk_quota=False))
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
    gw = backend.exec(name, ["sh", "-c", "ip route | awk '/default/{print $3}'"], user="root",
                      timeout_s=5).output.strip()
    assert gw
    r = backend.exec(name, ["bash", "-c", f"timeout 3 bash -c '</dev/tcp/{gw}/22'"], user="student",
                     timeout_s=10)
    assert r.exit_code != 0
    web = backend.exec(name, ["curl", "-sS", "-o", "/dev/null", "-w", "%{http_code}", "https://github.com"],
                       user="student", timeout_s=15)
    assert web.output.strip().startswith(("2", "3"))


def test_disk_cap_and_tty_session_cleanup():
    """Том места с квотой (как в deploy.sh): запись сверх размера не проходит; закрытый терминал не оставляет процессов."""
    import subprocess
    img = f"/tmp/trainer-test-{uuid.uuid4().hex[:6]}.img"
    vol = "trainer-home-test-" + uuid.uuid4().hex[:6]
    subprocess.run(["truncate", "-s", "64M", img], check=True)
    subprocess.run(["mkfs.ext4", "-q", "-F", img], check=True)
    subprocess.run(["docker", "volume", "create", "--driver", "local", "--opt", "type=ext4", "--opt", f"device={img}",
                    "--opt", "o=loop", vol], check=True, capture_output=True)
    backend = DockerBackend(Settings(_env_file=None))
    name = f"trainer-sbx-test-{uuid.uuid4().hex[:6]}"
    try:
        backend.ensure(name, {"LESSON_PASSWORD": "kot-les-dom"}, vol)
        time.sleep(1)
        r = backend.exec(name, ["dd", "if=/dev/zero", "of=/home/student/big", "bs=1M", "count=200"], user="student",
                         timeout_s=20)
        assert r.exit_code != 0 and "space" in r.output
        before = backend.exec(name, ["sh", "-c", "ps -e --no-headers | wc -l"], user="root", timeout_s=5).output
        for _ in range(5):
            tty = backend.attach_tty(name, "lobby")
            tty.write(b"sleep 1000 &\n")
            time.sleep(0.3)
            tty.close()
        time.sleep(1.5)
        after = backend.exec(name, ["sh", "-c", "ps -e --no-headers | wc -l"], user="root", timeout_s=5).output
        assert int(after) <= int(before) + 1
        r = backend.exec(name, ["bash", "-c", "setsid sleep 100 &"], user="student", timeout_s=3)
        assert r.exit_code == 0  # и не висит до таймаута клиента docker
    finally:
        backend.remove(name, vol, wipe=False)
        subprocess.run(["docker", "volume", "rm", "-f", vol], capture_output=True)
        subprocess.run(["rm", "-f", img])
