"""Вход: логин/пароль → cookie сессии + CSRF; выход; смена пароля."""
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import Engine

from apps.api.auth import COOKIE, account_dep
from apps.api.deps import engine_dep, settings_dep
from trainer.accounts.passwords import problems
from trainer.accounts.sessions import SessionStore, Throttle, client_ip
from trainer.accounts.store import AccountStore
from trainer.settings import Settings

router = APIRouter(prefix="/auth")


class LoginBody(BaseModel):
    login: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=512)


def _me(account, session) -> dict:
    return {"account": {"id": account.id, "login": account.login, "name": account.name, "role": account.role,
                        "must_change_password": account.must_change_password}, "csrf": session.csrf}


@router.post("/login")
def login(body: LoginBody, request: Request, response: Response, settings: Settings = Depends(settings_dep),
          engine: Engine = Depends(engine_dep)) -> dict:
    accounts, sessions, throttle = AccountStore(engine), SessionStore(engine), Throttle(engine)
    ip = client_ip(request)
    wait = throttle.blocked(body.login, ip)
    if wait:
        raise HTTPException(status_code=429, detail=f"слишком много попыток — повторите через {wait // 60 + 1} мин")
    account = accounts.check_password(body.login, body.password)
    if account is None:
        throttle.fail(body.login, ip)
        raise HTTPException(status_code=401, detail="неверный логин или пароль")
    throttle.clear(body.login)
    token, session = sessions.open(account.id, ip=ip, user_agent=request.headers.get("user-agent", ""))
    response.set_cookie(COOKIE, token, httponly=True, secure=settings.session_cookie_secure, samesite="strict",
                        path="/", max_age=int(sessions.max_age.total_seconds()))
    for hook in login_hooks:
        hook(engine, settings, account)
    return _me(account, session)


# действия после входа (например, поднять песочницу ученика); регистрируются модулями API
login_hooks: list = []
logout_hooks: list = []


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, who=Depends(account_dep),
           engine: Engine = Depends(engine_dep)) -> None:
    SessionStore(engine).close(request.cookies.get(COOKIE, ""))
    response.delete_cookie(COOKIE, path="/")
    for hook in logout_hooks:
        hook(engine, who[0])


@router.get("/me")
def me(who=Depends(account_dep)) -> dict:
    return _me(*who)


class PasswordBody(BaseModel):
    old: str = Field(min_length=1, max_length=512)
    new: str = Field(min_length=1, max_length=512)


@router.post("/password", status_code=204)
def change_password(body: PasswordBody, request: Request, who=Depends(account_dep),
                    engine: Engine = Depends(engine_dep)) -> None:
    account, session = who
    accounts, throttle, ip = AccountStore(engine), Throttle(engine), client_ip(request)
    if throttle.blocked(account.login, ip):
        raise HTTPException(status_code=429, detail="слишком много попыток — повторите позже")
    if accounts.check_password(account.login, body.old) is None:
        throttle.fail(account.login, ip)
        raise HTTPException(status_code=403, detail="текущий пароль неверен")
    issues = problems(body.new, account.login)
    if issues:
        raise HTTPException(status_code=422, detail=issues)
    accounts.set_password(account.id, body.new, must_change=False)
    SessionStore(engine).close_others(account.id, session.id)
