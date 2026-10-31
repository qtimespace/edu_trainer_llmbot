"""Уроки группы: описание пишет преподаватель, задания по нему готовит методист."""
from dataclasses import dataclass

from sqlalchemy import Engine, text

from trainer.accounts.store import is_uuid
from trainer.classroom.groups import GroupStore


@dataclass(frozen=True)
class Lesson:
    id: str
    title: str
    description: str
    position: int
    prep_status: str
    prep_error: str


def _lesson(r) -> Lesson:
    return Lesson(str(r.id), r.title, r.description, r.position, r.prep_status, r.prep_error)


class LessonStore:
    def __init__(self, engine: Engine):
        self._engine = engine

    def create(self, title: str, description: str) -> Lesson:
        group = GroupStore(self._engine).current()
        if group is None:
            raise KeyError("сначала создайте группу")
        with self._engine.begin() as c:
            r = c.execute(text("""INSERT INTO lessons (group_id, title, description, position)
                                  VALUES (:g, :t, :d, (SELECT COALESCE(max(position), 0) + 1 FROM lessons))
                                  RETURNING *"""), {"g": group.id, "t": title, "d": description}).first()
        return _lesson(r)

    def update(self, lesson_id: str, title: str | None = None, description: str | None = None) -> Lesson | None:
        if not is_uuid(lesson_id):
            return None
        with self._engine.begin() as c:
            r = c.execute(text("""UPDATE lessons SET title = COALESCE(:t, title), description = COALESCE(:d, description)
                                  WHERE id = CAST(:i AS uuid) RETURNING *"""),
                          {"i": lesson_id, "t": title, "d": description}).first()
        return _lesson(r) if r else None

    def list(self) -> list[Lesson]:
        with self._engine.connect() as c:
            return [_lesson(r) for r in c.execute(text("SELECT * FROM lessons ORDER BY position, created_at"))]

    def get(self, lesson_id: str) -> Lesson | None:
        if not is_uuid(lesson_id):
            return None
        with self._engine.connect() as c:
            r = c.execute(text("SELECT * FROM lessons WHERE id = CAST(:i AS uuid)"), {"i": lesson_id}).first()
        return _lesson(r) if r else None

    def set_prep(self, lesson_id: str, status: str, error: str = "") -> None:
        with self._engine.begin() as c:
            c.execute(text("UPDATE lessons SET prep_status = :s, prep_error = :e WHERE id = CAST(:i AS uuid)"),
                      {"i": lesson_id, "s": status, "e": error[:4000]})

    def try_start_prep(self, lesson_id: str) -> bool:
        """Атомарно idle|failed → running; False — подготовка уже идёт."""
        with self._engine.begin() as c:
            return c.execute(text("""UPDATE lessons SET prep_status = 'running', prep_error = ''
                                     WHERE id = CAST(:i AS uuid) AND prep_status <> 'running'"""),
                             {"i": lesson_id}).rowcount == 1
