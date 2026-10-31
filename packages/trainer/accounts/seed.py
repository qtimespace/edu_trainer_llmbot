"""Преподаватель из окружения: TRAINER_TEACHER_LOGIN / TRAINER_TEACHER_PASSWORD (.env).

Создаётся при старте API; если уже есть — пароль, роль и активность приводятся к окружению.
"""
from __future__ import annotations

from .passwords import problems
from .store import AccountStore


def seed_teacher(store: AccountStore, login: str, password: str) -> str:
    """created | updated | unchanged | skipped (не задано) | weak (пароль не по правилам)."""
    login = login.strip()
    if not login or not password:
        return "skipped"
    if problems(password, login):
        return "weak"
    account = store.by_login(login)
    if account is None:
        store.create_account(login, password, name=login, role="teacher")
        return "created"
    changed = False
    if account.role != "teacher" or not account.active:
        store.update(account.id, active=True, role="teacher")
        changed = True
    if account.must_change_password or store.check_password(login, password) is None:
        store.set_password(account.id, password)
        changed = True
    return "updated" if changed else "unchanged"
