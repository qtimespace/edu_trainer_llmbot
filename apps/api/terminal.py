"""Терминал в браузере: WebSocket ↔ оболочка lobby в песочнице ученика.

Только ученик и только своя песочница (никаких id в адресе); вход — по cookie сессии, Origin — только панель.
Кадры: клиент → бинарные = ввод, текст {"type":"resize","cols","rows"}; сервер → бинарные = вывод.
"""
import asyncio
import json
import logging
import threading

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.concurrency import run_in_threadpool

from apps.api.auth import COOKIE, account_from_cookie
from apps.api.deps import engine_dep, settings_dep
from apps.api.sandbox import get_backend
from trainer.sandbox.manager import NoSandbox, SandboxManager

log = logging.getLogger(__name__)
router = APIRouter()


def _resolve(dep):
    """Зависимость с учётом подмен в тестах (у WebSocket-маршрута их разрешаем сами)."""
    from apps.api.main import app
    return app.dependency_overrides.get(dep, dep)


@router.websocket("/ws/terminal")
async def terminal(ws: WebSocket) -> None:
    settings = _resolve(settings_dep)()
    engine = _resolve(engine_dep)(settings) if _resolve(engine_dep) is engine_dep else _resolve(engine_dep)()
    if ws.headers.get("origin") != settings.public_origin:
        await ws.close(code=4403)
        return
    found = await run_in_threadpool(account_from_cookie, ws.cookies.get(COOKIE, ""), engine)
    if found is None:
        await ws.close(code=4401)
        return
    account = found[0]
    if account.role != "student":
        await ws.close(code=4403)
        return
    try:
        tty = await run_in_threadpool(SandboxManager(get_backend(settings), engine).tty, account.id)
    except NoSandbox:
        await ws.close(code=4403)
        return
    await ws.accept()
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[bytes | None] = asyncio.Queue()
    stop = threading.Event()

    def pump() -> None:  # вывод оболочки → очередь (блокирующее чтение — в своём потоке)
        try:
            while not stop.is_set():
                data = tty.read(0.1)
                if data is None:
                    break
                if data:
                    loop.call_soon_threadsafe(queue.put_nowait, data)
            loop.call_soon_threadsafe(queue.put_nowait, None)
        except RuntimeError:  # соединение уже закрыто, цикл событий остановлен
            pass

    threading.Thread(target=pump, daemon=True).start()

    async def to_client() -> None:
        while (data := await queue.get()) is not None:
            await ws.send_bytes(data)
        await ws.close()

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
                if cmd.get("type") == "resize":
                    tty.resize(int(cmd.get("cols", 80)), int(cmd.get("rows", 24)))
                elif cmd.get("type") == "input":  # текстовый ввод (на случай клиента без бинарных кадров)
                    await run_in_threadpool(tty.write, str(cmd.get("data", "")).encode())

    sender, receiver = asyncio.create_task(to_client()), asyncio.create_task(from_client())
    try:
        await asyncio.wait({sender, receiver}, return_when=asyncio.FIRST_COMPLETED)
    except WebSocketDisconnect:
        pass
    finally:
        stop.set()
        tty.close()
        for task in (sender, receiver):
            task.cancel()
