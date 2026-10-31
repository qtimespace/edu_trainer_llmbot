"""Задания ученика. Черновик (draft) готовит методист; ученику — только одобренные, без проверочных команд."""
import json
from dataclasses import dataclass, field

from pydantic import BaseModel, Field
from sqlalchemy import Engine, text

from trainer.accounts.store import is_uuid

STATUSES = ("draft", "todo", "in_progress", "waiting_student", "done")
TRANSITIONS = {("draft", "todo"), ("todo", "in_progress"), ("in_progress", "waiting_student"),
               ("waiting_student", "in_progress"), ("in_progress", "done"), ("waiting_student", "done")}


class Check(BaseModel):
    cmd: str = Field(min_length=1, max_length=1000)
    about: str = Field(default="", max_length=300)


@dataclass(frozen=True)
class Task:
    id: str
    lesson_id: str
    student_id: str
    agent_key: str
    title: str
    statement: str
    status: str
    position: int
    checks: list[Check] = field(default_factory=list)

    def for_student(self) -> dict:
        """Вид для ученика: проверочные команды не показываем."""
        return {"id": self.id, "lesson_id": self.lesson_id, "agent_key": self.agent_key, "title": self.title,
                "statement": self.statement, "status": self.status, "position": self.position}

    def for_teacher(self) -> dict:
        return {**self.for_student(), "student_id": self.student_id, "checks": [c.model_dump() for c in self.checks]}


def _task(r) -> Task:
    return Task(id=str(r.id), lesson_id=str(r.lesson_id), student_id=str(r.student_id), agent_key=r.agent_key,
                title=r.title, statement=r.statement, status=r.status, position=r.position,
                checks=[Check(**c) for c in r.checks])


def _checks_json(checks: list[Check]) -> str:
    return json.dumps([c.model_dump() for c in checks], ensure_ascii=False)


_ORDER = " ORDER BY l.position, t.position, t.created_at"
_SELECT = "SELECT t.* FROM tasks t JOIN lessons l ON l.id = t.lesson_id"


class TaskStore:
    def __init__(self, engine: Engine):
        self._engine = engine

    def create_draft(self, lesson_id: str, student_id: str, agent_key: str, title: str, statement: str,
                     checks: list[Check], position: int = 0) -> Task:
        with self._engine.begin() as c:
            r = c.execute(text("""INSERT INTO tasks (lesson_id, student_id, agent_key, title, statement, checks, position)
                                  VALUES (CAST(:l AS uuid), CAST(:s AS uuid), :a, :t, :st, CAST(:c AS jsonb), :p)
                                  RETURNING *"""),
                          {"l": lesson_id, "s": student_id, "a": agent_key, "t": title, "st": statement,
                           "c": _checks_json(checks), "p": position}).first()
        return _task(r)

    def replace_drafts(self, lesson_id: str, student_id: str, drafts: list[dict]) -> list[Task]:
        """Новые черновики ученика по уроку вместо прежних (одобренные задания не трогаются)."""
        with self._engine.begin() as c:
            c.execute(text("""DELETE FROM tasks WHERE lesson_id = CAST(:l AS uuid) AND student_id = CAST(:s AS uuid)
                              AND status = 'draft'"""), {"l": lesson_id, "s": student_id})
        return [self.create_draft(lesson_id, student_id, d["agent_key"], d["title"], d["statement"], d["checks"],
                                  position=i + 1) for i, d in enumerate(drafts)]

    def get(self, task_id: str) -> Task | None:
        if not is_uuid(task_id):
            return None
        with self._engine.connect() as c:
            r = c.execute(text("SELECT * FROM tasks WHERE id = CAST(:i AS uuid)"), {"i": task_id}).first()
        return _task(r) if r else None

    def update(self, task_id: str, *, title: str | None = None, statement: str | None = None,
               checks: list[Check] | None = None, agent_key: str | None = None) -> Task:
        task = self.get(task_id)
        if task is None:
            raise KeyError(task_id)
        if task.status not in ("draft", "todo"):
            raise ValueError("задание уже в работе — менять нельзя")
        with self._engine.begin() as c:
            r = c.execute(text("""UPDATE tasks SET title = COALESCE(:t, title), statement = COALESCE(:st, statement),
                                      checks = COALESCE(CAST(:c AS jsonb), checks), agent_key = COALESCE(:a, agent_key),
                                      updated_at = now()
                                  WHERE id = CAST(:i AS uuid) RETURNING *"""),
                          {"i": task_id, "t": title, "st": statement, "a": agent_key,
                           "c": _checks_json(checks) if checks is not None else None}).first()
        return _task(r)

    def set_status(self, task_id: str, status: str) -> Task:
        task = self.get(task_id)
        if task is None:
            raise KeyError(task_id)
        if (task.status, status) not in TRANSITIONS:
            raise ValueError(f"нельзя перевести задание из {task.status} в {status}")
        with self._engine.begin() as c:
            r = c.execute(text("""UPDATE tasks SET status = :s, updated_at = now()
                                  WHERE id = CAST(:i AS uuid) AND status = :old RETURNING *"""),
                          {"i": task_id, "s": status, "old": task.status}).first()
        if r is None:
            raise ValueError("статус задания изменился одновременно — повторите")
        return _task(r)

    def approve(self, task_id: str) -> Task:
        return self.set_status(task_id, "todo")

    def approve_lesson(self, lesson_id: str, student_id: str | None = None) -> int:
        with self._engine.begin() as c:
            return c.execute(text("""UPDATE tasks SET status = 'todo', updated_at = now()
                                     WHERE lesson_id = CAST(:l AS uuid) AND status = 'draft'
                                       AND (CAST(:s AS uuid) IS NULL OR student_id = CAST(:s AS uuid))"""),
                             {"l": lesson_id, "s": student_id}).rowcount

    def delete(self, task_id: str) -> bool:
        if not is_uuid(task_id):
            return False
        with self._engine.begin() as c:
            return c.execute(text("DELETE FROM tasks WHERE id = CAST(:i AS uuid)"), {"i": task_id}).rowcount > 0

    def for_lesson(self, lesson_id: str) -> list[Task]:
        with self._engine.connect() as c:
            return [_task(r) for r in c.execute(text(_SELECT + " WHERE t.lesson_id = CAST(:l AS uuid)" + _ORDER),
                                                {"l": lesson_id})]

    def for_student(self, student_id: str) -> list[Task]:
        with self._engine.connect() as c:
            return [_task(r) for r in c.execute(text(
                _SELECT + " WHERE t.student_id = CAST(:s AS uuid) AND t.status <> 'draft'" + _ORDER), {"s": student_id})]

    def get_for_student(self, task_id: str, student_id: str) -> Task | None:
        task = self.get(task_id)
        if task is None or task.student_id != student_id or task.status == "draft":
            return None
        return task
