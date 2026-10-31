"""Сессии панели и ограничение попыток входа (перенос из DocOps, без проектов).

В cookie — случайный токен, в БД — только его SHA-256; сессия продлевается при активности, но живёт не дольше
`max_age` от создания.
"""
import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import Engine, text

_LOOPBACK = {"127.0.0.1", "::1", "localhost"}


def client_ip(request) -> str:
    """Адрес для ограничения попыток; "" — неизвестен, и тогда ограничение только по логину.

    Панель ходит в API через прокси Next: все её запросы приходят с loopback, и общий счётчик по такому адресу закрыл
    бы вход всем. Заголовки клиента не смотрим: прямой клиент считается по адресу сокета. Прокси Next не ставит
    X-Forwarded-For, а клиентский пропускает как есть, — поэтому API за ним запускают с `--no-proxy-headers`, иначе
    uvicorn подменит loopback адресом из заголовка клиента.
    """
    host = request.client.host if request.client else ""
    return "" if host in _LOOPBACK else host


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Session:
    id: str
    account_id: str
    csrf: str
    created_at: datetime
    expires_at: datetime


def _session(r) -> Session:
    return Session(id=str(r.id), account_id=str(r.account_id), csrf=r.csrf, created_at=r.created_at, expires_at=r.expires_at)


class SessionStore:
    def __init__(self, engine: Engine, ttl: timedelta = timedelta(hours=12), max_age: timedelta = timedelta(days=7)):
        self._engine, self.ttl, self.max_age = engine, ttl, max_age

    def open(self, account_id: str, ip: str = "", user_agent: str = "") -> tuple[str, Session]:
        token = secrets.token_urlsafe(32)
        now = datetime.now(UTC)
        with self._engine.begin() as c:
            r = c.execute(text("""
                INSERT INTO sessions (token_hash, account_id, csrf, ip, user_agent, expires_at)
                VALUES (:t, CAST(:a AS uuid), :csrf, :ip, :ua, :exp) RETURNING *"""),
                {"t": _hash(token), "a": account_id, "csrf": secrets.token_urlsafe(24),
                 "ip": ip[:64], "ua": user_agent[:256], "exp": now + min(self.ttl, self.max_age)}).first()
        return token, _session(r)

    def get(self, token: str) -> Session | None:
        if not token:
            return None
        now = datetime.now(UTC)
        with self._engine.begin() as c:
            r = c.execute(text("SELECT * FROM sessions WHERE token_hash = :t"), {"t": _hash(token)}).first()
            if r is None:
                return None
            if r.expires_at <= now or r.created_at + self.max_age <= now:
                c.execute(text("DELETE FROM sessions WHERE id = :i"), {"i": r.id})
                return None
            expires = min(now + self.ttl, r.created_at + self.max_age)
            r = c.execute(text("UPDATE sessions SET last_seen = :n, expires_at = :e WHERE id = :i RETURNING *"),
                          {"i": r.id, "n": now, "e": expires}).first()
        return _session(r)

    def close(self, token: str) -> None:
        with self._engine.begin() as c:
            c.execute(text("DELETE FROM sessions WHERE token_hash = :t"), {"t": _hash(token)})

    def close_others(self, account_id: str, keep_id: str) -> None:
        with self._engine.begin() as c:
            c.execute(text("DELETE FROM sessions WHERE account_id = CAST(:a AS uuid) AND id <> CAST(:k AS uuid)"),
                      {"a": account_id, "k": keep_id})

    def close_all(self, account_id: str) -> None:
        with self._engine.begin() as c:
            c.execute(text("DELETE FROM sessions WHERE account_id = CAST(:a AS uuid)"), {"a": account_id})


class Throttle:
    """10 неудач за 15 минут по логину или по IP — вход закрыт до конца окна."""

    def __init__(self, engine: Engine, limit: int = 10, window: timedelta = timedelta(minutes=15)):
        self._engine, self.limit, self.window = engine, limit, window

    def blocked(self, login: str, ip: str) -> int | None:
        since = datetime.now(UTC) - self.window
        with self._engine.connect() as c:
            for column, value in (("login", login.strip().lower()), ("ip", ip)):
                if not value:
                    continue  # неизвестный адрес — без счётчика по IP
                r = c.execute(text(f"SELECT count(*) AS n, min(at) AS first FROM login_attempts"
                                   f" WHERE {column} = :v AND at > :s"), {"v": value, "s": since}).first()
                if r.n >= self.limit:
                    return max(1, int((r.first + self.window - datetime.now(UTC)).total_seconds()))
        return None

    def fail(self, login: str, ip: str) -> None:
        with self._engine.begin() as c:
            c.execute(text("INSERT INTO login_attempts (login, ip) VALUES (:l, :i)"),
                      {"l": login.strip().lower(), "i": ip})
            c.execute(text("DELETE FROM login_attempts WHERE at < :old"),
                      {"old": datetime.now(UTC) - self.window * 4})

    def clear(self, login: str) -> None:
        with self._engine.begin() as c:
            c.execute(text("DELETE FROM login_attempts WHERE login = :l"), {"l": login.strip().lower()})
