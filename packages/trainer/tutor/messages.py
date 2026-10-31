"""Переписка ученика с агентом по заданию. Ученику — без проверочных команд и служебных полей."""
import json
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import Engine, text


@dataclass(frozen=True)
class Message:
    id: str
    task_id: str
    author: str
    agent_key: str | None
    text: str
    created_at: datetime
    meta: dict = field(default_factory=dict)

    def for_student(self) -> dict:
        checks = [{"about": c.get("about", ""), "passed": bool(c.get("passed"))} for c in self.meta.get("checks", [])]
        return {"id": self.id, "author": self.author, "agent_key": self.agent_key, "text": self.text,
                "created_at": self.created_at.isoformat(), "checks": checks}


def _message(r) -> Message:
    return Message(str(r.id), str(r.task_id), r.author, r.agent_key, r.text, r.created_at, dict(r.meta))


class MessageStore:
    def __init__(self, engine: Engine):
        self._engine = engine

    def add(self, task_id: str, author: str, text_: str, agent_key: str | None = None, meta: dict | None = None) -> None:
        with self._engine.begin() as c:
            c.execute(text("""INSERT INTO task_messages (task_id, author, agent_key, text, meta)
                              VALUES (CAST(:t AS uuid), :a, :k, :x, CAST(:m AS jsonb))"""),
                      {"t": task_id, "a": author, "k": agent_key, "x": text_,
                       "m": json.dumps(meta or {}, ensure_ascii=False)})

    def for_task(self, task_id: str, limit: int = 200) -> list[Message]:
        with self._engine.connect() as c:
            rows = c.execute(text("""SELECT * FROM (SELECT * FROM task_messages WHERE task_id = CAST(:t AS uuid)
                                     ORDER BY created_at DESC LIMIT :n) m ORDER BY created_at"""),
                             {"t": task_id, "n": limit})
            return [_message(r) for r in rows]

    def agent_feed(self, student_id: str, limit: int = 50) -> list[tuple[Message, str]]:
        """Ответы агентов и системные сообщения по всем заданиям ученика (окно «ответы LLM» преподавателя)."""
        with self._engine.connect() as c:
            rows = c.execute(text("""SELECT m.*, t.title FROM task_messages m JOIN tasks t ON t.id = m.task_id
                                     WHERE t.student_id = CAST(:s AS uuid) AND m.author <> 'student'
                                     ORDER BY m.created_at DESC LIMIT :n"""), {"s": student_id, "n": limit})
            return [(_message(r), r.title) for r in rows][::-1]
