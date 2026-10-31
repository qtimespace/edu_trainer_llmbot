"""Агенты тренажёра: методист (готовит задания) и тьюторы (ведут ученика). Всё настраивает преподаватель."""
import json
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import Engine, text

Kind = Literal["methodist", "tutor"]


class AgentInUse(Exception):
    """На агента ссылаются задания — удалить нельзя, только выключить."""


class Agent(BaseModel):
    key: str = Field(pattern=r"^[a-z][a-z0-9_-]{1,40}$")
    name: str = Field(min_length=1, max_length=60)
    kind: Kind
    system_prompt: str = Field(default="", max_length=20000)
    route: list[str] = Field(default_factory=list)  # ключи моделей каталога по порядку; пусто — любые подходящие
    max_usd_per_call: float = Field(default=0.05, gt=0, le=5)
    enabled: bool = True


def _agent(r) -> Agent:
    return Agent(key=r.key, name=r.name, kind=r.kind, system_prompt=r.system_prompt, route=list(r.route),
                 max_usd_per_call=float(r.max_usd_per_call), enabled=r.enabled)


class AgentStore:
    def __init__(self, engine: Engine):
        self._engine = engine

    def list(self, kind: str | None = None, enabled_only: bool = False) -> list[Agent]:
        sql = "SELECT * FROM agents WHERE (CAST(:k AS text) IS NULL OR kind = CAST(:k AS text)) AND (NOT CAST(:e AS boolean) OR enabled) ORDER BY kind, key"
        with self._engine.connect() as c:
            return [_agent(r) for r in c.execute(text(sql), {"k": kind, "e": enabled_only})]

    def get(self, key: str) -> Agent | None:
        with self._engine.connect() as c:
            r = c.execute(text("SELECT * FROM agents WHERE key = :k"), {"k": key}).first()
        return _agent(r) if r else None

    def upsert(self, agent: Agent) -> Agent:
        with self._engine.begin() as c:
            c.execute(text("""
                INSERT INTO agents (key, name, kind, system_prompt, route, max_usd_per_call, enabled)
                VALUES (:key, :name, :kind, :system_prompt, CAST(:route AS jsonb), :max_usd_per_call, :enabled)
                ON CONFLICT (key) DO UPDATE SET name = EXCLUDED.name, kind = EXCLUDED.kind,
                    system_prompt = EXCLUDED.system_prompt, route = EXCLUDED.route,
                    max_usd_per_call = EXCLUDED.max_usd_per_call, enabled = EXCLUDED.enabled, updated_at = now()"""),
                {**agent.model_dump(), "route": json.dumps(agent.route)})
        return agent

    def delete(self, key: str) -> bool:
        with self._engine.begin() as c:
            if c.execute(text("SELECT 1 FROM tasks WHERE agent_key = :k LIMIT 1"), {"k": key}).first():
                raise AgentInUse(f"агент {key} ведёт задания — его можно только выключить")
            return c.execute(text("DELETE FROM agents WHERE key = :k"), {"k": key}).rowcount > 0
