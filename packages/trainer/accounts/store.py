"""SQL учётных записей (перенос из DocOps без проектов и ролей в проектах)."""
from __future__ import annotations

import uuid

from sqlalchemy import Engine, text
from sqlalchemy.exc import IntegrityError

from .models import Account
from .passwords import hash_password, verify_password

_DUMMY = hash_password("dummy password for timing")  # одинаковое время ответа на неизвестный логин


class LoginTaken(Exception):
    """Логин уже занят (без учёта регистра)."""


def _account(r) -> Account:
    return Account(id=str(r.id), login=r.login, name=r.name, role=r.role, active=r.active,
                   must_change_password=r.must_change_password, created_at=r.created_at)


def is_uuid(value: str | None) -> bool:
    try:
        uuid.UUID(str(value))
    except ValueError:
        return False
    return True


class AccountStore:
    def __init__(self, engine: Engine):
        self._engine = engine

    def create_account(self, login: str, password: str, name: str = "", role: str = "student",
                       must_change: bool = False) -> Account:
        try:
            with self._engine.begin() as c:
                r = c.execute(text("""
                    INSERT INTO accounts (login, name, password_hash, role, must_change_password)
                    VALUES (:l, :n, :h, :r, :m) RETURNING *"""),
                    {"l": login.strip(), "n": name, "h": hash_password(password), "r": role, "m": must_change}).first()
        except IntegrityError as e:
            raise LoginTaken(f"логин «{login}» уже занят") from e
        return _account(r)

    def get(self, account_id: str) -> Account | None:
        if not is_uuid(account_id):
            return None
        with self._engine.connect() as c:
            r = c.execute(text("SELECT * FROM accounts WHERE id = CAST(:i AS uuid)"), {"i": account_id}).first()
        return _account(r) if r else None

    def by_login(self, login: str) -> Account | None:
        with self._engine.connect() as c:
            r = c.execute(text("SELECT * FROM accounts WHERE lower(login) = lower(:l)"), {"l": login.strip()}).first()
        return _account(r) if r else None

    def check_password(self, login: str, password: str) -> Account | None:
        with self._engine.connect() as c:
            r = c.execute(text("SELECT * FROM accounts WHERE lower(login) = lower(:l)"), {"l": login.strip()}).first()
        if r is None:
            verify_password(_DUMMY, password)
            return None
        if not verify_password(r.password_hash, password) or not r.active:
            return None
        return _account(r)

    def set_password(self, account_id: str, password: str, must_change: bool = False) -> None:
        with self._engine.begin() as c:
            c.execute(text("""
                UPDATE accounts SET password_hash = :h, must_change_password = :m, password_changed_at = now()
                WHERE id = CAST(:i AS uuid)"""), {"i": account_id, "h": hash_password(password), "m": must_change})

    def update(self, account_id: str, *, name: str | None = None, active: bool | None = None,
               role: str | None = None) -> None:
        with self._engine.begin() as c:
            c.execute(text("""
                UPDATE accounts SET name = COALESCE(:n, name), active = COALESCE(:a, active), role = COALESCE(:r, role)
                WHERE id = CAST(:i AS uuid)"""), {"i": account_id, "n": name, "a": active, "r": role})
