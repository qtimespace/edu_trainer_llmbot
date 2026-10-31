from typing import Protocol

from pydantic import BaseModel
from sqlalchemy import Engine, text


class LedgerEntry(BaseModel):
    request_id: str
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    agent: str
    task_id: str
    user_id: str | None = None
    project_id: str | None = None
    model_key: str | None = None  # ключ модели реестра — по нему считаются лимиты модели


class Ledger(Protocol):
    def record(self, entry: LedgerEntry) -> None: ...


class InMemoryLedger:
    def __init__(self):
        self.entries: list[LedgerEntry] = []

    def record(self, entry: LedgerEntry) -> None:
        self.entries.append(entry)


_INSERT = text("""
INSERT INTO ledger (request_id, provider, model, input_tokens, output_tokens, cost_usd, agent, task_id,
                    user_id, project_id, model_key)
VALUES (:request_id, :provider, :model, :input_tokens, :output_tokens, :cost_usd, :agent, :task_id,
        :user_id, :project_id, :model_key)
""")


class PostgresLedger:
    """Расход пишется на пользователя и проект запуска (спека 3.0b §5): видно, что потратила автоматика."""

    def __init__(self, engine: Engine, user_id: str | None = None, project_id: str | None = None,
                 agent_prefix: str = ""):
        self._engine = engine
        self._agent_prefix = agent_prefix
        self._user_id = user_id
        self._project_id = project_id

    def record(self, entry: LedgerEntry) -> None:
        row = entry.model_dump()
        row["user_id"] = row["user_id"] or self._user_id
        row["project_id"] = row["project_id"] or self._project_id
        row["agent"] = self._agent_prefix + row["agent"]
        with self._engine.begin() as c:
            c.execute(_INSERT, row)
