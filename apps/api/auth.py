"""Кто делает запрос: сессия панели (cookie + CSRF) → учётная запись; роли teacher/student (fail-closed)."""
from fastapi import Depends, HTTPException, Request
from sqlalchemy import Engine

from apps.api.deps import engine_dep
from trainer.accounts.models import Account
from trainer.accounts.sessions import Session, SessionStore
from trainer.accounts.store import AccountStore

COOKIE = "trainer_session"
SAFE = {"GET", "HEAD", "OPTIONS"}


def account_from_cookie(token: str, engine: Engine) -> tuple[Account, Session] | None:
    """Сессия по токену cookie (используется и WebSocket-ом терминала, где нет CSRF)."""
    session = SessionStore(engine).get(token)
    if session is None:
        return None
    account = AccountStore(engine).get(session.account_id)
    if account is None or not account.active:
        return None
    return account, session


def account_dep(request: Request, engine: Engine = Depends(engine_dep)) -> tuple[Account, Session]:
    """Учётная запись по cookie; изменяющие запросы — с `X-CSRF-Token`."""
    found = account_from_cookie(request.cookies.get(COOKIE, ""), engine)
    if found is None:
        raise HTTPException(status_code=401, detail="войдите в тренажёр")
    account, session = found
    if request.method not in SAFE and request.headers.get("X-CSRF-Token") != session.csrf:
        raise HTTPException(status_code=403, detail="нет CSRF-токена — обновите страницу")
    return account, session


def _role(role: str):
    def dep(who: tuple[Account, Session] = Depends(account_dep)) -> Account:
        account = who[0]
        if account.must_change_password:
            raise HTTPException(status_code=403, detail="смените пароль")
        if account.role != role:
            raise HTTPException(status_code=403, detail="недостаточно прав")
        return account
    return dep


teacher_dep = _role("teacher")
student_dep = _role("student")


def any_role_dep(who: tuple[Account, Session] = Depends(account_dep)) -> Account:
    return who[0]
