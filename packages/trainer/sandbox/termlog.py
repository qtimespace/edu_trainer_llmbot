"""Экран терминала ученика для преподавателя: вывод оболочки (в нём и эхо введённого, и сессия на lab после ssh)
пишется кусками по пути через API — ученик запись не подменит. Храним последние KEEP_BYTES вывода на ученика и размер
окна, чтобы полноэкранные программы (nano) проигрывались как у ученика. Пароль терминал не показывает — в запись
он не попадает."""
import threading
import time
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import Engine, text

KEEP_BYTES = 2 * 1024 * 1024
FLUSH_BYTES, FLUSH_SECONDS = 16 * 1024, 1.0


@dataclass(frozen=True)
class Chunk:
    id: int
    kind: str  # out — вывод; size — окно «колонкиxстроки»
    data: bytes
    at: datetime


class TerminalLog:
    def __init__(self, engine: Engine, keep_bytes: int = KEEP_BYTES):
        self._engine, self._keep = engine, keep_bytes

    def size(self, account_id: str, cols: int, rows: int) -> None:
        self._add(account_id, "size", f"{cols}x{rows}".encode())

    def append(self, account_id: str, data: bytes) -> None:
        if data:
            self._add(account_id, "out", data)
            self._prune(account_id)

    def since(self, account_id: str, after: int = 0, limit: int = 2000) -> list[Chunk]:
        with self._engine.connect() as c:
            rows = c.execute(text("""SELECT id, kind, data, at FROM terminal_log
                                     WHERE account_id = CAST(:a AS uuid) AND id > :after ORDER BY id LIMIT :n"""),
                             {"a": account_id, "after": after, "n": limit})
            return [Chunk(r.id, r.kind, bytes(r.data), r.at) for r in rows]

    def _add(self, account_id: str, kind: str, data: bytes) -> None:
        with self._engine.begin() as c:
            c.execute(text("INSERT INTO terminal_log (account_id, kind, data) VALUES (CAST(:a AS uuid), :k, :d)"),
                      {"a": account_id, "k": kind, "d": data})

    def _prune(self, account_id: str) -> None:
        """Свежие куски вывода, пока не наберётся keep_bytes; размер окна, действующий для самого старого из них, — тоже."""
        with self._engine.begin() as c:
            cut = c.execute(text("""SELECT min(id) FROM (
                                      SELECT id, sum(octet_length(data)) OVER (ORDER BY id DESC) - octet_length(data) AS newer
                                      FROM terminal_log WHERE account_id = CAST(:a AS uuid) AND kind = 'out') s
                                    WHERE newer < :keep"""), {"a": account_id, "keep": self._keep}).scalar()
            if cut is None:
                return
            c.execute(text("""DELETE FROM terminal_log WHERE account_id = CAST(:a AS uuid) AND id < :cut
                              AND id IS DISTINCT FROM (SELECT max(id) FROM terminal_log WHERE account_id = CAST(:a AS uuid)
                                                       AND kind = 'size' AND id < :cut)"""), {"a": account_id, "cut": cut})


class Recorder:
    """Копит вывод и пишет кусками (FLUSH_BYTES или раз в FLUSH_SECONDS); ошибка записи терминал не роняет."""

    def __init__(self, log: TerminalLog, account_id: str, on_error=None):
        self._log, self._id, self._on_error = log, account_id, on_error
        self._buf, self._since = bytearray(), time.monotonic()
        self._lock = threading.Lock()  # вывод пишет поток чтения, размер окна — обработчик WebSocket

    def feed(self, data: bytes) -> None:
        with self._lock:
            self._buf += data
            due = len(self._buf) >= FLUSH_BYTES or (self._buf and time.monotonic() - self._since >= FLUSH_SECONDS)
        if due:
            self.flush()

    def flush(self) -> None:
        with self._lock:
            data, self._buf, self._since = bytes(self._buf), bytearray(), time.monotonic()
        if not data:
            return
        try:
            self._log.append(self._id, data)
        except Exception as e:  # noqa: BLE001
            if self._on_error:
                self._on_error(e)

    def size(self, cols: int, rows: int) -> None:
        self.flush()  # вывод до смены размера — со старым размером
        try:
            self._log.size(self._id, cols, rows)
        except Exception as e:  # noqa: BLE001
            if self._on_error:
                self._on_error(e)
