"""Терминал в браузере: WebSocket ↔ оболочка lobby в песочнице ученика.

Только ученик и только своя песочница (никаких id в адресе); вход — по cookie сессии, Origin — только панель.
Кадры: клиент → бинарные = ввод, текст {"type":"resize","cols","rows"}; сервер → бинарные = вывод.
"""
import asyncio
import json
import logging
import threading

from fastapi import APIRouter, WebSocket
from starlette.concurrency import run_in_threadpool

from apps.api.auth import COOKIE, account_from_cookie, role_problem
from apps.api.deps import engine_dep, settings_dep
from apps.api.sandbox import get_backend
from trainer.sandbox.manager import NoSandbox, SandboxManager

log = logging.getLogger(__name__)
router = APIRouter()
QUEUE_CHUNKS = 64  # вывод копится не больше 64 кусков: `yes` в терминале не съест память API


def _resolve(dep):
    """Зависимость с учётом подмен в тестах (у WebSocket-маршрута их разрешаем сами)."""
    from apps.api.main import app
    return app.dependency_overrides.get(dep, dep)


def _clamp(value, low: int, high: int, default: int) -> int:
    try:
        return max(low, min(high, int(value)))
    except (TypeError, ValueError):
        return default


@router.websocket("/ws/terminal")
async def terminal(ws: WebSocket) -> None:
    settings = _resolve(settings_dep)()
    engine = engine_dep(settings) if _resolve(engine_dep) is engine_dep else _resolve(engine_dep)()
    if ws.headers.get("origin") != settings.public_origin:
        await ws.close(code=4403)
        return
    found = await run_in_threadpool(account_from_cookie, ws.cookies.get(COOKIE, ""), engine)
    if found is None:
        await ws.close(code=4401)
        return
    account = found[0]
    if role_problem(account, "student"):
        await ws.close(code=4403)
        return
    try:
        tty = await run_in_threadpool(SandboxManager(get_backend(settings), engine).tty, account.id)
    except NoSandbox:
        await ws.close(code=4403)
        return
    await ws.accept()
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[bytes | None] = asyncio.Queue(maxsize=QUEUE_CHUNKS)
    stop = threading.Event()

    def put(item: bytes | None, timeout: float | None = None) -> None:
        coro = queue.put(item)
        try:
            future = asyncio.run_coroutine_threadsafe(coro, loop)
        except RuntimeError:  # цикл событий уже остановлен
            coro.close()
            raise
        future.result(timeout=timeout)

    def pump() -> None:  # вывод оболочки → очередь; полная очередь притормаживает чтение (backpressure)
        try:
            while not stop.is_set():
                data = tty.read(0.1)
                if data is None:
                    break
                if data:
                    put(data)
            put(None, timeout=1)
        except Exception:  # noqa: BLE001 — соединение закрыто, цикл событий остановлен
            pass

    threading.Thread(target=pump, daemon=True).start()

    async def to_client() -> None:
        while (data := await queue.get()) is not None:
            await ws.send_bytes(data)

    async def from_client() -> None:
        while True:
            msg = await ws.receive()
            if msg["type"] == "websocket.disconnect":
                return
            if msg.get("bytes"):
                await run_in_threadpool(tty.write, msg["bytes"])
            elif msg.get("text"):
                try:
                    cmd = json.loads(msg["text"])
                except ValueError:
                    continue
                if not isinstance(cmd, dict):
                    continue
                if cmd.get("type") == "resize":
                    cols, rows = _clamp(cmd.get("cols"), 1, 500, 80), _clamp(cmd.get("rows"), 1, 200, 24)
                    await run_in_threadpool(tty.resize, cols, rows)
                elif cmd.get("type") == "input":  # текстовый ввод (на случай клиента без бинарных кадров)
                    await run_in_threadpool(tty.write, str(cmd.get("data", "")).encode())

    sender, receiver = asyncio.create_task(to_client()), asyncio.create_task(from_client())
    try:
        done, _ = await asyncio.wait({sender, receiver}, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            if task.exception() is not None and not isinstance(task.exception(), asyncio.CancelledError):
                log.warning("терминал %s: %r", account.login, task.exception())
    finally:
        stop.set()
        for task in (sender, receiver):
            task.cancel()
        await run_in_threadpool(tty.close)
        try:
            await ws.close()
        except Exception:  # noqa: BLE001 — уже закрыто клиентом
            pass
