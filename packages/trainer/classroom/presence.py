"""Кто в сети: вкладка панели пингует раз в 15 с; онлайн — пинг не старше 40 с (свет в комнате)."""
from datetime import UTC, datetime, timedelta

from sqlalchemy import Engine, text

ONLINE_WINDOW = timedelta(seconds=40)


class PresenceStore:
    def __init__(self, engine: Engine):
        self._engine = engine

    def ping(self, account_id: str, now: datetime | None = None) -> None:
        with self._engine.begin() as c:
            c.execute(text("""INSERT INTO presence (account_id, last_seen) VALUES (CAST(:a AS uuid), :n)
                              ON CONFLICT (account_id) DO UPDATE SET last_seen = EXCLUDED.last_seen"""),
                      {"a": account_id, "n": now or datetime.now(UTC)})

    def online(self, account_ids: list[str], now: datetime | None = None) -> set[str]:
        if not account_ids:
            return set()
        since = (now or datetime.now(UTC)) - ONLINE_WINDOW
        with self._engine.connect() as c:
            rows = c.execute(text("""SELECT account_id FROM presence
                                     WHERE account_id::text = ANY(:ids) AND last_seen >= :s"""),
                             {"ids": list(account_ids), "s": since})
            return {str(r.account_id) for r in rows}

    def drop(self, account_id: str) -> None:
        with self._engine.begin() as c:
            c.execute(text("DELETE FROM presence WHERE account_id = CAST(:a AS uuid)"), {"a": account_id})
