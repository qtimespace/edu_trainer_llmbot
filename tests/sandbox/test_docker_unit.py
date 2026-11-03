"""DockerBackend без настоящего Docker: поддельный клиент. Проверяем то, что ломало бы урок на сервере."""
import socket
import threading
from types import SimpleNamespace

import pytest

from trainer.sandbox.docker_backend import DockerBackend, DockerTty, SandboxDiskError
from trainer.settings import Settings


class FakeContainers:
    def __init__(self):
        self.runs, self.boxes = [], {}

    def get(self, name):
        import docker.errors
        if name not in self.boxes:
            raise docker.errors.NotFound(name)
        return self.boxes[name]

    def run(self, image, **kw):
        self.runs.append(kw)
        self.boxes[kw["name"]] = Box(image_id=IMAGE_ID)


IMAGE_ID = "sha256:new"


class Box:
    status = "running"

    def __init__(self, image_id=IMAGE_ID):
        self.execs, self.image, self.removed = [], SimpleNamespace(id=image_id), False

    def remove(self, force=False):
        self.removed = True

    def exec_run(self, cmd, **kw):
        self.execs.append((cmd, kw))
        return SimpleNamespace(exit_code=0, output=b"ok")


class FakeVolumes:
    def __init__(self, names):
        self.names = set(names)

    def get(self, name):
        import docker.errors
        if name not in self.names:
            raise docker.errors.NotFound(name)
        return SimpleNamespace(name=name)


def _backend(volumes=("trainer-home-seat1",), quota=True):
    b = DockerBackend.__new__(DockerBackend)
    b._settings = Settings(_env_file=None, sandbox_disk_quota=quota)
    b._network_ready = True
    b._client = SimpleNamespace(containers=FakeContainers(), volumes=FakeVolumes(volumes),
                                images=SimpleNamespace(get=lambda name: SimpleNamespace(id=IMAGE_ID)))
    return b


def test_sandbox_has_capped_tmp_and_needs_prepared_home_volume():
    b = _backend()
    b.ensure("box", {}, "trainer-home-seat1")
    kw = b._client.containers.runs[0]
    assert "size=" in kw["tmpfs"]["/tmp"] and "size=" in kw["tmpfs"]["/var/tmp"] and kw["shm_size"]
    with pytest.raises(SandboxDiskError):  # без заранее созданного тома с квотой песочница не стартует
        _backend(volumes=()).ensure("box2", {}, "trainer-home-seat2")
    _backend(volumes=(), quota=False).ensure("box3", {}, "x")  # разработка без квоты — можно


def test_sandbox_init_reaps_zombies():
    """PID 1 — init Docker: убитые при закрытии вкладки фоновые процессы не копятся зомби в лимите процессов."""
    b = _backend()
    b.ensure("box", {}, "trainer-home-seat1")
    assert b._client.containers.runs[0]["init"] is True


def test_check_output_goes_through_file_so_detached_process_cannot_hold_exec():
    b = _backend()
    b.ensure("box", {}, "trainer-home-seat1")
    b.exec("box", ["bash", "-c", "setsid sleep 100 &"], user="student", timeout_s=10)
    cmd, _ = b._client.containers.boxes["box"].execs[0]
    script = " ".join(cmd)
    assert "timeout" in script and ">" in script and "setsid sleep 100 &" in cmd


def test_tty_close_kills_its_session():
    killed = []
    a, b = socket.socketpair()
    tty = DockerTty(SimpleNamespace(exec_resize=lambda *x, **k: None), "exec1", a, on_close=lambda: killed.append(1))
    tty.close()
    b.close()
    assert killed == [1]


def test_tty_large_paste_does_not_break():
    a, b = socket.socketpair()
    tty = DockerTty(SimpleNamespace(), "exec1", a)
    got = bytearray()

    def drain():
        while len(got) < 2_000_000:
            chunk = b.recv(65536)
            if not chunk:
                break
            got.extend(chunk)
    t = threading.Thread(target=drain)
    t.start()
    tty.write(b"x" * 2_000_000)  # неблокирующий сокет бросил бы BlockingIOError
    t.join(5)
    tty.close()
    b.close()
    assert len(got) == 2_000_000


def test_sandbox_on_an_old_image_is_recreated_on_login_and_home_kept():
    """Новый образ (например, с node) доходит до уже созданных песочниц при следующем входе; /home — на томе."""
    b = _backend()
    old = Box(image_id="sha256:old")
    b._client.containers.boxes["box"] = old
    b.ensure("box", {}, "trainer-home-seat1")
    assert old.removed and b._client.containers.runs  # пересоздана; том не трогали (wipe не вызывался)
    fresh = b._client.containers.boxes["box"]
    b.ensure("box", {}, "trainer-home-seat1")
    assert not fresh.removed and len(b._client.containers.runs) == 1  # на свежем образе — не пересоздаётся
