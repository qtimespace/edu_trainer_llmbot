"""Лимиты моделей и провайдеров на ключ пользователя и пауза после 429 (спека 2026-10-19-llm-limits).

Охранник решает, можно ли звать модель сейчас: пауза модели или провайдера, либо лимит запросов/токенов в минуту и
в сутки не выдержит запрос. Расход и паузы — в источниках: в памяти (тесты) или в Postgres (журнал расходов, паузы).
"""
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC
from email.utils import parsedate_to_datetime
from typing import TYPE_CHECKING, Protocol

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from .registry import ModelSpec

MAX_WAIT_SECONDS = 60.0  # дольше шлюз не ждёт — ошибка «на паузе до …»
WAIT_SLACK = 1.5  # окна считает Postgres, ждёт воркер: запас на расхождение часов (ревью)
RATE_LIMIT_PAUSE = 60.0  # 429 без Retry-After
QUOTA_PAUSE = 3600.0  # квота провайдера исчерпана (402, «нет средств»)


class Limits(BaseModel):
    rpm: int | None = Field(default=None, gt=0)
    rpd: int | None = Field(default=None, gt=0)
    tpm: int | None = Field(default=None, gt=0)
    tpd: int | None = Field(default=None, gt=0)


@dataclass(frozen=True)
class Window:
    requests: int = 0
    tokens: int = 0
    oldest: float | None = None  # время самой старой записи окна — когда она выйдет, место освободится


class UsageSource(Protocol):
    def window(self, scope: str, key: str, seconds: float) -> Window: ...
    def add(self, scope: str, key: str, tokens: int, at: float | None = None) -> None: ...


class CooldownStore(Protocol):
    def get(self, scope: str, key: str) -> tuple[float, str] | None: ...
    def set(self, scope: str, key: str, until: float, reason: str) -> None: ...


@dataclass
class InMemoryUsage:
    clock: Callable[[], float] = time.time
    records: list[tuple[str, str, int, float]] = field(default_factory=list)

    def add(self, scope: str, key: str, tokens: int, at: float | None = None) -> None:
        self.records.append((scope, key, tokens, self.clock() if at is None else at))

    def window(self, scope: str, key: str, seconds: float) -> Window:
        since = self.clock() - seconds
        hits = [(t, at) for s, k, t, at in self.records if s == scope and k == key and at > since]
        return Window(len(hits), sum(t for t, _ in hits), min((at for _, at in hits), default=None))


@dataclass
class InMemoryCooldowns:
    clock: Callable[[], float] = time.time
    items: dict[tuple[str, str], tuple[float, str]] = field(default_factory=dict)

    def get(self, scope: str, key: str) -> tuple[float, str] | None:
        item = self.items.get((scope, key))
        return item if item and item[0] > self.clock() else None

    def set(self, scope: str, key: str, until: float, reason: str) -> None:
        self.items[(scope, key)] = (until, reason)


_CHECKS = (("rpm", 60, "запросов в минуту"), ("rpd", 86400, "запросов в сутки"),
           ("tpm", 60, "токенов в минуту"), ("tpd", 86400, "токенов в сутки"))
_SCOPE = {"model": "модели", "provider": "провайдера"}


class LimitGuard:
    def __init__(self, usage: UsageSource, cooldowns: CooldownStore, provider_limits: dict[str, Limits] | None = None,
                 clock: Callable[[], float] = time.time, sleep: Callable[[float], None] = time.sleep):
        self.usage, self.cooldowns = usage, cooldowns
        self.provider_limits = provider_limits or {}
        self.clock, self._sleep = clock, sleep

    def blocked(self, spec: "ModelSpec", tokens: int) -> tuple[float | None, str] | None:
        """(до какого времени, почему) — модель сейчас звать нельзя; None — можно. Время — самое позднее из
        мешающих (освободится rpm, а tpd держит часы — ждать rpm бессмысленно); None вместо времени — запрос больше
        самого лимита токенов, ожиданием не пройдёт."""
        found: list[tuple[float, str]] = []
        for scope, key in (("model", spec.key), ("provider", spec.provider)):
            paused = self.cooldowns.get(scope, key)
            if paused:
                found.append((paused[0], f"пауза {_SCOPE[scope]} {key}: {paused[1]}"))
        now = self.clock()
        for limits, scope, key in ((spec.limits, "model", spec.key),
                                   (self.provider_limits.get(spec.provider), "provider", spec.provider)):
            if limits is None:
                continue
            for name, seconds, label in _CHECKS:
                limit = getattr(limits, name)
                if limit is None:
                    continue
                if name.startswith("t") and tokens > limit:
                    return None, (f"запрос ~{tokens} токенов больше лимита {_SCOPE[scope]} {key}: {limit} {label} — "
                                  "поднимите лимит или выход агента")
                w = self.usage.window(scope, key, seconds)
                used = w.requests + 1 if name.startswith("r") else w.tokens + tokens
                if used > limit:
                    found.append(((w.oldest or now) + seconds, f"лимит {_SCOPE[scope]} {key}: {limit} {label}"))
        return max(found, key=lambda x: x[0]) if found else None

    def on_success(self, spec: "ModelSpec", tokens: int) -> None:
        self.usage.add("model", spec.key, tokens)
        self.usage.add("provider", spec.provider, tokens)

    def on_error(self, spec: "ModelSpec", kind: str, retry_after: float | None = None) -> None:
        now = self.clock()
        if kind == "rate_limit":
            self.cooldowns.set("model", spec.key, now + (retry_after if retry_after is not None else RATE_LIMIT_PAUSE),
                               "429 от провайдера (слишком много запросов)")
        elif kind == "quota_exceeded":
            self.cooldowns.set("provider", spec.provider, now + QUOTA_PAUSE,
                               "квота провайдера исчерпана (нет средств или лимит ключа)")

    def wait_until(self, until: float) -> bool:
        """Подождать до `until`, если это не дольше MAX_WAIT_SECONDS. → ждали ли."""
        delay = until - self.clock()
        if delay > MAX_WAIT_SECONDS:
            return False
        self._sleep(max(delay, 0.0) + WAIT_SLACK)
        return True


def retry_after_seconds(value: str | None, now: float | None = None) -> float | None:
    """Заголовок Retry-After: секунды или дата HTTP. Непонятное — None (пауза по умолчанию)."""
    if not value:
        return None
    value = value.strip()
    if value.isdigit():
        return float(value)
    try:
        when = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    return max(when.timestamp() - (time.time() if now is None else now), 0.0)


class PgUsage:
    """Расход ключа пользователя — по журналу расходов (`ledger`): запись делает шлюз, отдельный счётчик не нужен."""

    def __init__(self, engine, user_id: str | None):
        self._engine, self._user = engine, user_id or ""

    def add(self, scope: str, key: str, tokens: int, at: float | None = None) -> None:
        return None  # успешный вызов уже записан в ledger

    def window(self, scope: str, key: str, seconds: float) -> Window:
        from sqlalchemy import text
        column = {"model": "model_key", "provider": "provider"}[scope]
        # тренажёр: ключ один на всех (преподавателя) — "*" считает расход всех учеников вместе
        who = "true" if self._user == "*" else "user_id = :u" if self._user else "user_id IS NULL"
        with self._engine.connect() as c:
            r = c.execute(text(
                f"SELECT count(*) AS reqs, COALESCE(sum(input_tokens + output_tokens), 0) AS toks,"
                f" min(extract(epoch FROM created_at)) AS oldest FROM ledger WHERE {who}"
                f" AND {column} = :k AND created_at > now() - make_interval(secs => :s)"),
                {"u": self._user, "k": key, "s": seconds}).one()
        return Window(int(r.reqs), int(r.toks), float(r.oldest) if r.oldest is not None else None)


class PgCooldowns:
    """Паузы моделей и провайдеров ключа пользователя — общие для API, воркера и автоматики."""

    def __init__(self, engine, user_id: str | None):
        self._engine, self._user = engine, user_id or ""

    def get(self, scope: str, key: str) -> tuple[float, str] | None:
        from sqlalchemy import text
        with self._engine.connect() as c:
            r = c.execute(text("SELECT extract(epoch FROM until) AS u, reason FROM llm_cooldowns WHERE user_id = :u"
                               " AND scope = :s AND key = :k AND until > now()"),
                          {"u": self._user, "s": scope, "k": key}).first()
        return (float(r.u), r.reason) if r else None

    def set(self, scope: str, key: str, until: float, reason: str) -> None:
        from sqlalchemy import text
        with self._engine.begin() as c:
            c.execute(text("INSERT INTO llm_cooldowns (user_id, scope, key, until, reason)"
                           " VALUES (:u, :s, :k, to_timestamp(:t), :r) ON CONFLICT (user_id, scope, key)"
                           # более короткий повторный 429 не укорачивает идущую паузу
                           " DO UPDATE SET until = GREATEST(llm_cooldowns.until, EXCLUDED.until),"
                           " reason = EXCLUDED.reason, created_at = now()"),
                      {"u": self._user, "s": scope, "k": key, "t": until, "r": reason})

    def active(self) -> list[dict]:
        from sqlalchemy import text
        with self._engine.connect() as c:
            rows = c.execute(text("SELECT scope, key, extract(epoch FROM until) AS u, reason FROM llm_cooldowns"
                                  " WHERE user_id = :u AND until > now() ORDER BY until"), {"u": self._user})
            return [{"scope": r.scope, "key": r.key, "until": float(r.u), "reason": r.reason} for r in rows]

    def clear(self, scope: str, key: str) -> bool:
        from sqlalchemy import text
        with self._engine.begin() as c:
            return c.execute(text("DELETE FROM llm_cooldowns WHERE user_id = :u AND scope = :s AND key = :k"),
                             {"u": self._user, "s": scope, "k": key}).rowcount > 0
