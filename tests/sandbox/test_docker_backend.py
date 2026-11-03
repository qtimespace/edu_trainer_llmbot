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


def test_fork_bomb_contained_and_reset_recovers(box):
    """Форк-бомба упирается в pids_limit своей песочницы; «Пересоздать мой сервер» (remove + ensure) её снимает."""
    backend, name = box
    backend.exec(name, ["bash", "-c", "timeout 5 bash -c ':(){ :|:& };:' || true"], user="student", timeout_s=15)
    container = backend._client.containers.get(name)
    assert int(container.stats(stream=False)["pids_stats"].get("current", 0)) <= backend._settings.sandbox_pids
    volume = next(m["Name"] for m in container.attrs["Mounts"] if m["Destination"] == "/home")
    backend.remove(name, volume, wipe=False)
    backend.ensure(name, {"LESSON_PASSWORD": "kot-les-dom"}, volume)
    time.sleep(1)
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
        # не `hostname -i`: имя хоста lab указывает на 127.0.0.1 — тест стучался бы в свой же sshd
        ip_b = backend.exec(b, ["sh", "-c", "ip -4 -o addr show eth0 | awk '{print $4}' | cut -d/ -f1"],
                            user="student", timeout_s=10).output.strip()
        assert ip_b.startswith("172.31.250.")
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
    tag = uuid.uuid4().hex[:6]
    img, mnt, vol = f"/tmp/trainer-test-{tag}.img", f"/tmp/trainer-test-{tag}", f"trainer-home-test-{tag}"
    subprocess.run(["truncate", "-s", "64M", img], check=True)
    subprocess.run(["mkfs.ext4", "-q", "-F", img], check=True)
    subprocess.run(["mkdir", "-p", mnt], check=True)
    subprocess.run(["mount", "-o", "loop,nodev,nosuid", img, mnt], check=True)
    subprocess.run(["docker", "volume", "create", "--driver", "local", "--opt", "type=none", "--opt", f"device={mnt}",
                    "--opt", "o=bind", vol], check=True, capture_output=True)
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
        subprocess.run(["umount", mnt])
        subprocess.run(["rm", "-rf", img, mnt])


def test_seat_volumes_mountable():
    """Тома мест из deploy.sh монтируются в контейнер (Docker сам loop не подключает — раньше падал вход ученика)."""
    import docker
    client = docker.from_env()
    seats = [v for v in client.volumes.list() if v.name.startswith("trainer-home-seat")]
    assert seats, "нет томов мест — запустите infra/deploy/deploy.sh"
    for v in seats:
        client.containers.run("trainer-sandbox:1", entrypoint=["df", "/home"], volumes={v.name: {"bind": "/home"}},
                              network_mode="none", remove=True)
