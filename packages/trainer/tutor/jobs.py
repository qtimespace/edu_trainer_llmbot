"""Ходы агентов: учёт «агент сейчас работает» (для офиса) и запуск фоновой работы потоком."""
import logging
import threading
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import Engine, text
from sqlalchemy.exc import IntegrityError

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Job:
    id: str
    agent_key: str
    task_id: str | None
    lesson_id: str | None
    student_id: str | None
    started_at: datetime


@dataclass(frozen=True)
class LlmDeps:
    """Всё, что нужно для вызова агентов: БД, настройки и (в тестах) подменённые провайдеры."""
    engine: Engine
    settings: object
    providers: dict | None = None


STALE_MINUTES = 5  # ход дольше — считаем зависшим (поток умер или песочница не ответила)


class JobStore:
    def __init__(self, engine: Engine):
        self._engine = engine

    def start(self, agent_key: str, *, task_id: str | None = None, lesson_id: str | None = None,
              student_id: str | None = None) -> str | None:
        """None — ход уже идёт: по этому заданию или по другому заданию того же ученика (частичные UNIQUE)."""
        if task_id is not None:  # зависший ход не блокирует задание до перезапуска API
            with self._engine.begin() as c:
                c.execute(text("""UPDATE agent_jobs SET status = 'failed', finished_at = now()
                                  WHERE status = 'running' AND task_id IS NOT NULL
                                    AND started_at < now() - make_interval(mins => :m)
                                    AND (task_id = CAST(:t AS uuid) OR student_id = CAST(:s AS uuid))"""),
                          {"m": STALE_MINUTES, "t": task_id, "s": student_id})
        try:
            with self._engine.begin() as c:
                return str(c.execute(text("""
                    INSERT INTO agent_jobs (agent_key, task_id, lesson_id, student_id)
                    VALUES (:a, CAST(:t AS uuid), CAST(:l AS uuid), CAST(:s AS uuid)) RETURNING id"""),
                    {"a": agent_key, "t": task_id, "l": lesson_id, "s": student_id}).scalar_one())
        except IntegrityError:
            return None

    def owns(self, job_id: str) -> bool:
        """Ход всё ещё за этим потоком (не закрыт как зависший и не отдан другому)."""
        with self._engine.connect() as c:
            return c.execute(text("SELECT 1 FROM agent_jobs WHERE id = CAST(:i AS uuid) AND status = 'running'"),
                             {"i": job_id}).first() is not None

    def finish(self, job_id: str, ok: bool) -> None:
        with self._engine.begin() as c:
            c.execute(text("UPDATE agent_jobs SET status = :s, finished_at = now()"
                           " WHERE id = CAST(:i AS uuid) AND status = 'running'"),
                      {"i": job_id, "s": "done" if ok else "failed"})

    def running(self, student_id: str | None = None) -> list[Job]:
        with self._engine.connect() as c:
            rows = c.execute(text("""SELECT * FROM agent_jobs WHERE status = 'running'
                                     AND (CAST(:s AS uuid) IS NULL OR student_id = CAST(:s AS uuid))"""),
                             {"s": student_id})
            return [Job(str(r.id), r.agent_key, str(r.task_id) if r.task_id else None,
                        str(r.lesson_id) if r.lesson_id else None, str(r.student_id) if r.student_id else None,
                        r.started_at) for r in rows]

    def is_running(self, task_id: str) -> bool:
        with self._engine.connect() as c:
            return c.execute(text("""SELECT 1 FROM agent_jobs WHERE task_id = CAST(:t AS uuid) AND status = 'running'
                                     AND started_at >= now() - make_interval(mins => :m)"""),
                             {"t": task_id, "m": STALE_MINUTES}).first() is not None

    def fail_stale(self) -> int:
        """После перезапуска API «зависшие» ходы закрываются: потоки умерли вместе с процессом."""
        with self._engine.begin() as c:
            return c.execute(text("UPDATE agent_jobs SET status = 'failed', finished_at = now()"
                                  " WHERE status = 'running'")).rowcount


def run_background(fn, *args) -> None:
    def target():
        try:
            fn(*args)
        except Exception:  # noqa: BLE001 — поток не должен умирать молча
            log.exception("фоновая работа %s упала", getattr(fn, "__name__", fn))
    threading.Thread(target=target, daemon=True).start()


def recover_after_restart(engine: Engine) -> None:
    """При старте API: ходы и подготовки уроков, прерванные перезапуском, не висят «в работе» вечно."""
    JobStore(engine).fail_stale()
    with engine.begin() as c:
        c.execute(text("UPDATE lessons SET prep_status = 'failed', prep_error = 'прервано перезапуском сервера'"
                       " WHERE prep_status = 'running'"))
