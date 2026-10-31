"""Песочницы на настоящем Docker (Docker SDK). Контейнер на ученика: лимиты, без портов наружу, без связи
с соседями (bridge без ICC), выход в интернет есть; домашние папки — именованный том /home."""
import logging
import select
import threading

from trainer.settings import Settings

from .backend import ExecResult, Status

log = logging.getLogger(__name__)
# sshd и chpasswd в контейнере работают от root: нужны только эти возможности
CAPS = ["CHOWN", "SETUID", "SETGID", "AUDIT_WRITE", "SYS_CHROOT", "DAC_OVERRIDE", "FOWNER", "KILL"]
_LOCK = threading.Lock()  # ensure одного контейнера из двух потоков (вход + терминал) не должен создать дубль


class DockerTty:
    def __init__(self, api, exec_id: str, sock):
        self._api, self._exec_id = api, exec_id
        self._sock = getattr(sock, "_sock", sock)  # docker-py отдаёт обёртку над сокетом
        self._sock.setblocking(False)
        self._closed = False

    def write(self, data: bytes) -> None:
        if not self._closed:
            self._sock.sendall(data)

    def read(self, timeout: float = 0.1) -> bytes | None:
        if self._closed:
            return None
        ready, _, _ = select.select([self._sock], [], [], timeout)
        if not ready:
            return b""
        try:
            data = self._sock.recv(65536)
        except (BlockingIOError, InterruptedError):
            return b""
        except OSError:
            data = b""
        if not data:  # оболочка завершилась (exit)
            self._closed = True
            return None
        return data

    def resize(self, cols: int, rows: int) -> None:
        try:
            self._api.exec_resize(self._exec_id, height=rows, width=cols)
        except Exception:  # noqa: BLE001 — ресайз до старта exec бывает отвергнут, не критично
            pass

    def close(self) -> None:
        self._closed = True
        try:
            self._sock.close()
        except OSError:
            pass


class DockerBackend:
    def __init__(self, settings: Settings):
        import docker
        self._settings = settings
        self._client = docker.DockerClient(base_url=settings.docker_url)
        self._network_ready = False

    def _ensure_network(self) -> None:
        if self._network_ready:
            return
        name = self._settings.sandbox_network
        if not self._client.networks.list(names=[name]):
            self._client.networks.create(name, driver="bridge",
                                         options={"com.docker.network.bridge.enable_icc": "false"})
        self._network_ready = True

    def _get(self, name: str):
        import docker.errors
        try:
            return self._client.containers.get(name)
        except docker.errors.NotFound:
            return None

    def ensure(self, name: str, env: dict[str, str], volume: str) -> None:
        with _LOCK:
            box = self._get(name)
            if box is not None:
                if box.status != "running":
                    box.start()
                return
            self._ensure_network()
            s = self._settings
            self._client.containers.run(
                s.sandbox_image, name=name, detach=True, environment=env, hostname="lab",
                volumes={volume: {"bind": "/home", "mode": "rw"}}, network=s.sandbox_network,
                extra_hosts={"lab": "127.0.0.1"}, mem_limit=s.sandbox_mem, memswap_limit=s.sandbox_mem,
                nano_cpus=int(s.sandbox_cpus * 1e9), pids_limit=s.sandbox_pids, cap_drop=["ALL"], cap_add=CAPS,
                restart_policy={"Name": "unless-stopped"}, labels={"trainer": "sandbox"})

    def remove(self, name: str, volume: str, wipe: bool) -> None:
        import docker.errors
        with _LOCK:
            box = self._get(name)
            if box is not None:
                box.remove(force=True)
            if wipe:
                try:
                    self._client.volumes.get(volume).remove(force=True)
                except docker.errors.NotFound:
                    pass

    def exec(self, name: str, cmd: list[str], user: str, timeout_s: int) -> ExecResult:
        box = self._get(name)
        if box is None:
            return ExecResult(127, "песочница не запущена")
        # timeout -k: зависшая проверка (бесконечный цикл ученика) не держит поток API дольше timeout_s
        res = box.exec_run(["timeout", "-k", "2", str(timeout_s), *cmd], user=user, demux=False)
        out = (res.output or b"").decode("utf-8", errors="replace")
        return ExecResult(res.exit_code if res.exit_code is not None else 1, out)

    def attach_tty(self, name: str, user: str) -> DockerTty:
        api = self._client.api
        exec_id = api.exec_create(name, ["bash", "-l"], stdin=True, tty=True, user=user,
                                  workdir=f"/home/{user}", environment={"TERM": "xterm-256color"})["Id"]
        sock = api.exec_start(exec_id, socket=True, tty=True)
        return DockerTty(api, exec_id, sock)

    def status(self, name: str) -> Status:
        box = self._get(name)
        if box is None:
            return "missing"
        return "running" if box.status == "running" else "stopped"
