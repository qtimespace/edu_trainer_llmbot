"""Группа (одна на тренажёр, 2–5 мест) и её ученики."""
from __future__ import annotations

import secrets
from dataclasses import dataclass

from sqlalchemy import Engine, text

from trainer.accounts.models import Account
from trainer.accounts.store import AccountStore

MIN_SIZE, MAX_SIZE = 2, 5
# учебный пароль ssh-урока: три простых слова — ребёнку легко набрать
_WORDS = ("kot", "les", "dom", "mir", "sok", "nos", "luk", "mak", "rak", "dub", "pol", "sol", "gol", "ris", "tok",
          "zub", "led", "mel", "nit", "pir", "rog", "sad", "tik", "vek", "yod", "fen", "gid", "kit", "lom", "mag")


class GroupFull(Exception):
    """Все места заняты."""


class SeatsTaken(Exception):
    """Нельзя уменьшить группу: места заняты."""


@dataclass(frozen=True)
class Group:
    id: str
    name: str
    size: int


@dataclass(frozen=True)
class Student:
    account_id: str
    login: str
    name: str
    seat: int
    note: str
    budget_usd: float
    lesson_password: str


def lesson_password() -> str:
    return "-".join(secrets.choice(_WORDS) for _ in range(3))


def login_password() -> str:
    return secrets.token_urlsafe(9)  # 12 символов


def _student(r) -> Student:
    return Student(account_id=str(r.account_id), login=r.login, name=r.name, seat=r.seat, note=r.note,
                   budget_usd=float(r.budget_usd), lesson_password=r.lesson_password)


_SELECT = """SELECT gs.*, a.login, a.name FROM group_students gs JOIN accounts a ON a.id = gs.account_id"""


class GroupStore:
    def __init__(self, engine: Engine):
        self._engine = engine

    def current(self) -> Group | None:
        with self._engine.connect() as c:
            r = c.execute(text("SELECT * FROM groups ORDER BY created_at LIMIT 1")).first()
        return Group(str(r.id), r.name, r.size) if r else None

    def create(self, name: str, size: int) -> Group:
        if self.current() is not None:
            raise ValueError("группа уже создана")
        with self._engine.begin() as c:
            r = c.execute(text("INSERT INTO groups (name, size) VALUES (:n, :s) RETURNING *"),
                          {"n": name, "s": size}).first()
        return Group(str(r.id), r.name, r.size)

    def resize(self, size: int, name: str | None = None) -> Group:
        group = self.current()
        if group is None:
            raise KeyError("группы нет")
        if any(s.seat > size for s in self.students()):
            raise SeatsTaken(f"места выше {size} заняты")
        with self._engine.begin() as c:
            r = c.execute(text("UPDATE groups SET size = :s, name = COALESCE(:n, name) WHERE id = :i RETURNING *"),
                          {"s": size, "n": name, "i": group.id}).first()
        return Group(str(r.id), r.name, r.size)

    def add_student(self, login: str, name: str, note: str = "") -> tuple[Account, str]:
        group = self.current()
        if group is None:
            raise KeyError("группы нет")
        taken = {s.seat for s in self.students()}
        free = [s for s in range(1, group.size + 1) if s not in taken]
        if not free:
            raise GroupFull("все места заняты")
        password = login_password()
        account = AccountStore(self._engine).create_account(login, password, name=name, role="student")
        with self._engine.begin() as c:
            c.execute(text("""INSERT INTO group_students (group_id, account_id, seat, note, lesson_password)
                              VALUES (:g, CAST(:a AS uuid), :s, :n, :p)"""),
                      {"g": group.id, "a": account.id, "s": free[0], "n": note, "p": lesson_password()})
        return account, password

    def students(self) -> list[Student]:
        with self._engine.connect() as c:
            return [_student(r) for r in c.execute(text(_SELECT + " ORDER BY gs.seat"))]

    def student(self, account_id: str) -> Student | None:
        from trainer.accounts.store import is_uuid
        if not is_uuid(account_id):
            return None
        with self._engine.connect() as c:
            r = c.execute(text(_SELECT + " WHERE gs.account_id = CAST(:a AS uuid)"), {"a": account_id}).first()
        return _student(r) if r else None

    def update_student(self, account_id: str, note: str | None = None, budget_usd: float | None = None,
                       name: str | None = None) -> None:
        with self._engine.begin() as c:
            c.execute(text("""UPDATE group_students SET note = COALESCE(:n, note), budget_usd = COALESCE(:b, budget_usd)
                              WHERE account_id = CAST(:a AS uuid)"""), {"a": account_id, "n": note, "b": budget_usd})
        if name is not None:
            AccountStore(self._engine).update(account_id, name=name)
