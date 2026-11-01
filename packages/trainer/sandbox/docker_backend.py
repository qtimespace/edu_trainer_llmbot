"""Песочницы на настоящем Docker (Docker SDK). Контейнер на ученика: лимиты памяти/CPU/процессов и диска, без портов
наружу, без связи с соседями (bridge без ICC), выход в интернет есть.

Диск: /home — заранее созданный том места ученика с ограниченным размером (ext4-образ через loop, см.
infra/deploy/deploy.sh), /tmp и /var/tmp — tmpfs с размером; ученик не root и больше никуда писать не может.
"""
import logging
import select
import socket
import threading
import uuid

from trainer.settings import Settings

from .backend import ExecResult, Status

log = logging.getLogger(__name__)
# sshd и chpasswd в контейнере работают от root: нужны только эти возможности
CAPS = ["CHOWN", "SETUID", "SETGID", "AUDIT_WRITE", "SYS_CHROOT", "DAC_OVERRIDE", "FOWNER", "KILL"]
_LOCK = threading.Lock()  # ensure одного контейнера из двух потоков (вход + терминал) не должен создать дубль
BRIDGE, SUBNET = "trbr-sandbox", "172.31.250.0/24"
OUTPUT_CAP = 65536
# вывод команды — через файл: процесс, ушедший в фон (setsid, nohup … &), не держит поток exec открытым
_EXEC = ('f=$(mktemp); timeout -k 2 "$0" "$@" >"$f" 2>&1; rc=$?; head -c ' + str(OUTPUT_CAP)
         + ' "$f"; rm -f "$f"; exit $rc')


class SandboxNetworkError(RuntimeError):
    """Сеть песочниц не та, на которую настроен межсетевой экран."""


class SandboxDiskError(RuntimeError):
    """Нет заранее созданного тома места ученика с квотой — песочницу без ограничения диска не запускаем."""


class DockerTty:
    def __init__(self, api, exec_id: str, sock, on_close=None):
        self._api, self._exec_id, self._on_close = api, exec_id, on_close
        self._sock = getattr(sock, "_sock", sock)  # docker-py отдаёт обёртку над сокетом
        # блокирующий с таймаутом: большая вставка в терминал дописывается целиком, а не рвёт соединение
        self._sock.settimeout(10)
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
        except (BlockingIOError, InterruptedError, socket.timeout):
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
        if self._closed and self._on_close is None:
            return
        self._closed = True
        try:
            self._sock.close()
        except OSError:
            pass
        on_close, self._on_close = self._on_close, None
        if on_close is not None:  # docker не убивает процессы exec при отключении клиента — убиваем сами
            try:
                on_close()
            except Exception:  # noqa: BLE001
                log.warning("сессия терминала не завершена", exc_info=True)


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
        existing = self._client.networks.list(names=[name])
        if existing:
            attrs = existing[0].attrs
            bridge = (attrs.get("Options") or {}).get("com.docker.network.bridge.name")
            subnets = [c.get("Subnet") for c in (attrs.get("IPAM") or {}).get("Config") or []]
            if bridge != BRIDGE or subnets != [SUBNET]:
                # экран завязан на мост и подсеть: в чужой сети песочницы остались бы без него — не запускаем
                raise SandboxNetworkError(f"сеть {name}: мост {bridge}, подсеть {subnets} — нужны {BRIDGE} и {SUBNET};"
                                          " удалите сеть и запустите infra/deploy/deploy.sh")
        else:
            import docker.types
            # мост и подсеть закреплены: на них завязан межсетевой экран (infra/deploy/sandbox-firewall.sh)
            ipam = docker.types.IPAMConfig(pool_configs=[docker.types.IPAMPool(subnet=SUBNET)])
            self._client.networks.create(name, driver="bridge", ipam=ipam, options={
                "com.docker.network.bridge.enable_icc": "false", "com.docker.network.bridge.name": BRIDGE})
        self._network_ready = True

    def _get(self, name: str):
        import docker.errors
        try:
            return self._client.containers.get(name)
        except docker.errors.NotFound:
            return None

    def _volume_exists(self, volume: str) -> bool:
        import docker.errors
        try:
            self._client.volumes.get(volume)
            return True
        except docker.errors.NotFound:
            return False

    def ensure(self, name: str, env: dict[str, str], volume: str) -> None:
        with _LOCK:
            box = self._get(name)
            if box is not None:
                if box.status != "running":
                    box.start()
                return
            s = self._settings
            if s.sandbox_disk_quota and not self._volume_exists(volume):
                raise SandboxDiskError(f"нет тома {volume} с ограничением размера — запустите infra/deploy/deploy.sh")
            self._ensure_network()
            tmp = f"size={s.sandbox_tmp_size},mode=1777"
            self._client.containers.run(
                s.sandbox_image, name=name, detach=True, environment=env, hostname="lab",
                volumes={volume: {"bind": "/home", "mode": "rw"}}, tmpfs={"/tmp": tmp, "/var/tmp": tmp},
                shm_size=s.sandbox_tmp_size, network=s.sandbox_network,
                extra_hosts={"lab": "127.0.0.1"}, mem_limit=s.sandbox_mem, memswap_limit=s.sandbox_mem,
                nano_cpus=int(s.sandbox_cpus * 1e9), pids_limit=s.sandbox_pids, cap_drop=["ALL"], cap_add=CAPS,
                restart_policy={"Name": "unless-stopped"}, labels={"trainer": "sandbox"})

    def remove(self, name: str, volume: str, wipe: bool) -> None:
        import docker.errors
        with _LOCK:
            box = self._get(name)
            if box is not None:
                box.remove(force=True)
            if not wipe:
                return
            if self._settings.sandbox_disk_quota:
                # том с квотой создан заранее (loop-образ) — не удаляем, а очищаем; домашние папки пересоздаст entrypoint
                self._client.containers.run(self._settings.sandbox_image, entrypoint=["find", "/home", "-mindepth", "1",
                                            "-delete"], volumes={volume: {"bind": "/home", "mode": "rw"}},
                                            network_mode="none", remove=True)
                return
            try:
                self._client.volumes.get(volume).remove(force=True)
            except docker.errors.NotFound:
                pass

    def exec(self, name: str, cmd: list[str], user: str, timeout_s: int) -> ExecResult:
        box = self._get(name)
        if box is None:
            return ExecResult(127, "песочница не запущена")
        # timeout -k: зависшая проверка (бесконечный цикл ученика) не держит поток API дольше timeout_s
        res = box.exec_run(["sh", "-c", _EXEC, str(timeout_s), *cmd], user=user, demux=False)
        out = (res.output or b"").decode("utf-8", errors="replace")
        return ExecResult(res.exit_code if res.exit_code is not None else 1, out)

    def attach_tty(self, name: str, user: str) -> DockerTty:
        api = self._client.api
        token = uuid.uuid4().hex
        pidfile = f"/tmp/.tty-{token}"
        # оболочка запоминает свой номер сессии: при закрытии вкладки завершаем её вместе с ssh и всем, что запущено
        exec_id = api.exec_create(name, ["bash", "-c", f"echo $$ > {pidfile}; exec bash -l"], stdin=True, tty=True,
                                  user=user, workdir=f"/home/{user}", environment={"TERM": "xterm-256color"})["Id"]
        sock = api.exec_start(exec_id, socket=True, tty=True)

        def kill_session() -> None:
            self.exec(name, ["sh", "-c", f'sid=$(cat {pidfile} 2>/dev/null) || exit 0; pkill -HUP -s "$sid";'
                                         f' sleep 1; pkill -KILL -s "$sid"; rm -f {pidfile}'], user="root", timeout_s=5)
        return DockerTty(api, exec_id, sock, on_close=kill_session)

    def status(self, name: str) -> Status:
        box = self._get(name)
        if box is None:
            return "missing"
        return "running" if box.status == "running" else "stopped"
