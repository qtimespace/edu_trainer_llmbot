"""Песочница ученика: протокол бэкенда и заглушка (FakeBackend) для разработки и тестов без Docker."""
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, Protocol

Status = Literal["running", "missing", "stopped"]


@dataclass(frozen=True)
class ExecResult:
    exit_code: int
    output: str


class TtySession(Protocol):
    def write(self, data: bytes) -> None: ...
    def read(self, timeout: float = 0.1) -> bytes | None: ...  # None — сессия закрыта; b"" — пока пусто
    def resize(self, cols: int, rows: int) -> None: ...
    def close(self) -> None: ...


class SandboxBackend(Protocol):
    def ensure(self, name: str, env: dict[str, str], volume: str) -> None: ...
    def remove(self, name: str, volume: str, wipe: bool) -> None: ...
    def exec(self, name: str, cmd: list[str], user: str, timeout_s: int) -> ExecResult: ...
    def attach_tty(self, name: str, user: str) -> TtySession: ...
    def status(self, name: str) -> Status: ...


class FakeTty:
    """Эхо-терминал: что написали, то и прочитаем."""

    def __init__(self):
        self.buffer, self.closed, self.size = b"", False, (80, 24)

    def write(self, data: bytes) -> None:
        self.buffer += data

    def read(self, timeout: float = 0.1) -> bytes | None:
        if self.closed:
            return None
        out, self.buffer = self.buffer, b""
        if not out:
            import time
            time.sleep(min(timeout, 0.02))
        return out

    def resize(self, cols: int, rows: int) -> None:
        self.size = (cols, rows)

    def close(self) -> None:
        self.closed = True


class FakeBackend:
    def __init__(self, handler: Callable[[str, list[str], str], ExecResult] | None = None):
        self.boxes: dict[str, dict] = {}
        self.volumes: dict[str, dict] = {}
        self.ttys: list[FakeTty] = []
        self.handler = handler or (lambda name, cmd, user: ExecResult(0, ""))
        self.calls: list[tuple[str, list[str], str]] = []

    def ensure(self, name: str, env: dict[str, str], volume: str) -> None:
        self.volumes.setdefault(volume, {})
        self.boxes.setdefault(name, {"env": dict(env), "volume": volume})

    def remove(self, name: str, volume: str, wipe: bool) -> None:
        self.boxes.pop(name, None)
        if wipe:
            self.volumes.pop(volume, None)

    def exec(self, name: str, cmd: list[str], user: str, timeout_s: int) -> ExecResult:
        self.calls.append((name, cmd, user))
        return self.handler(name, cmd, user)

    def attach_tty(self, name: str, user: str) -> FakeTty:
        tty = FakeTty()
        self.ttys.append(tty)
        return tty

    def status(self, name: str) -> Status:
        return "running" if name in self.boxes else "missing"
