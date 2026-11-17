"""Кто в сети и куда смотрит: вкладка панели пингует раз в 15 с и сразу при смене состояния.

Онлайн — пинг не старше 40 с (свет в комнате); у скрытой вкладки — 150 с: браузер будит её таймеры раз в минуту.
Внимание ученика (focused — вкладка открыта и окно в фокусе, blurred — окно не в фокусе, hidden — вкладка скрыта
или браузер свёрнут) пишется лентой переходов; перерыв без пингов — событие offline, в итоги он не входит.
"""
from datetime import UTC, datetime, timedelta
from typing import Literal

from sqlalchemy import Engine, text

ONLINE_WINDOW = timedelta(seconds=40)
HIDDEN_WINDOW = timedelta(seconds=150)
State = Literal["focused", "blurred", "hidden"]
STATES = ("focused", "blurred", "hidden")


def _window(state: str | None) -> timedelta:
    return HIDDEN_WINDOW if state == "hidden" else ONLINE_WINDOW


class PresenceStore:
    def __init__(self, engine: Engine):
        self._engine = engine

    def ping(self, account_id: str, now: datetime | None = None, state: State | None = None) -> None:
        now = now or datetime.now(UTC)
        with self._engine.begin() as c:
            prev = c.execute(text("SELECT last_seen, attention FROM presence WHERE account_id = CAST(:a AS uuid) "
                                  "FOR UPDATE"), {"a": account_id}).first()
            c.execute(text("""INSERT INTO presence (account_id, last_seen, attention)
                              VALUES (CAST(:a AS uuid), :n, :s)
                              ON CONFLICT (account_id) DO UPDATE SET last_seen = EXCLUDED.last_seen,
                                  attention = COALESCE(EXCLUDED.attention, presence.attention)"""),
                      {"a": account_id, "n": now, "s": state})
            if state is None:
                return
            gap = prev is not None and prev.last_seen < now - _window(prev.attention)
            if gap and prev.attention:  # вкладку закрывали — перерыв с последнего пинга
                self._log(c, account_id, "offline", prev.last_seen)
            if gap or prev is None or prev.attention != state:
                self._log(c, account_id, state, now)

    @staticmethod
    def _log(c, account_id: str, state: str, at: datetime) -> None:
        c.execute(text("INSERT INTO attention_log (account_id, state, at) VALUES (CAST(:a AS uuid), :s, :t)"),
                  {"a": account_id, "s": state, "t": at})

    def online(self, account_ids: list[str], now: datetime | None = None) -> set[str]:
        if not account_ids:
            return set()
        now = now or datetime.now(UTC)
        with self._engine.connect() as c:
            rows = c.execute(text("""SELECT account_id FROM presence WHERE account_id::text = ANY(:ids)
                                     AND (last_seen >= :s OR (attention = 'hidden' AND last_seen >= :h))"""),
                             {"ids": list(account_ids), "s": now - ONLINE_WINDOW, "h": now - HIDDEN_WINDOW})
            return {str(r.account_id) for r in rows}

    def current(self, account_ids: list[str], now: datetime | None = None) -> dict[str, dict]:
        """Состояние онлайн-учеников: {id: {"state", "since"}} — для табличек в офисе."""
        if not account_ids:
            return {}
        now = now or datetime.now(UTC)
        with self._engine.connect() as c:
            rows = c.execute(text("""SELECT p.account_id, p.attention,
                                        (SELECT max(at) FROM attention_log l WHERE l.account_id = p.account_id) AS since
                                     FROM presence p WHERE p.account_id::text = ANY(:ids) AND p.attention IS NOT NULL
                                       AND (p.last_seen >= :s OR (p.attention = 'hidden' AND p.last_seen >= :h))"""),
                             {"ids": list(account_ids), "s": now - ONLINE_WINDOW, "h": now - HIDDEN_WINDOW})
            return {str(r.account_id): {"state": r.attention, "since": r.since.isoformat() if r.since else None}
                    for r in rows}

    def attention(self, account_id: str, since: datetime, now: datetime | None = None) -> dict:
        """Сейчас, лента переходов и сколько секунд в каждом состоянии с `since` (например, с начала дня)."""
        now = now or datetime.now(UTC)
        with self._engine.connect() as c:
            p = c.execute(text("SELECT last_seen, attention FROM presence WHERE account_id = CAST(:a AS uuid)"),
                          {"a": account_id}).first()
            rows = c.execute(text("""SELECT state, at FROM attention_log WHERE account_id = CAST(:a AS uuid)
                                     AND at >= COALESCE((SELECT max(at) FROM attention_log
                                                         WHERE account_id = CAST(:a AS uuid) AND at <= :since), :since)
                                     ORDER BY at, id"""), {"a": account_id, "since": since}).all()
        online = p is not None and p.attention is not None and p.last_seen >= now - _window(p.attention)
        end = min(now, p.last_seen + _window(p.attention)) if p is not None else now
        totals = dict.fromkeys(STATES, 0)
        for i, r in enumerate(rows):
            stop = rows[i + 1].at if i + 1 < len(rows) else end
            start = max(r.at, since)
            if r.state in totals and stop > start:
                totals[r.state] += int((stop - start).total_seconds())
        last = rows[-1] if rows else None
        return {"state": p.attention if online else "offline",
                "since": (last.at if online and last else p.last_seen if p else now).isoformat(),
                "totals": totals,
                "events": [{"state": r.state, "at": r.at.isoformat()} for r in rows if r.at >= since][-200:]}

    def drop(self, account_id: str) -> None:
        """Выход из учётки: не в сети сразу; в ленте — перерыв, чтобы время до следующего входа не считалось."""
        with self._engine.begin() as c:
            gone = c.execute(text("DELETE FROM presence WHERE account_id = CAST(:a AS uuid) RETURNING attention"),
                             {"a": account_id}).first()
            if gone is not None and gone.attention:
                self._log(c, account_id, "offline", datetime.now(UTC))
