"""Группа и ученики (только преподаватель)."""
from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import Engine

from apps.api.auth import teacher_dep
from apps.api.deps import engine_dep
from trainer.accounts.sessions import SessionStore
from trainer.accounts.store import AccountStore, LoginTaken
from trainer.classroom.groups import MAX_SIZE, MIN_SIZE, GroupFull, GroupStore, SeatsTaken, login_password

router = APIRouter(prefix="/group", dependencies=[Depends(teacher_dep)])


class GroupBody(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    size: int = Field(ge=MIN_SIZE, le=MAX_SIZE)


class ResizeBody(BaseModel):
    size: int = Field(ge=MIN_SIZE, le=MAX_SIZE)
    name: str | None = Field(default=None, min_length=1, max_length=100)


class StudentBody(BaseModel):
    login: str = Field(min_length=2, max_length=64, pattern=r"^[A-Za-z0-9._-]+$")
    name: str = Field(min_length=1, max_length=100)
    note: str = Field(default="", max_length=2000)


class StudentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    note: str | None = Field(default=None, max_length=2000)
    budget_usd: float | None = Field(default=None, ge=0, le=100)


def _group_or_404(store: GroupStore):
    group = store.current()
    if group is None:
        raise HTTPException(status_code=404, detail="группа ещё не создана")
    return group


@router.get("")
def get_group(engine: Engine = Depends(engine_dep)) -> dict:
    store = GroupStore(engine)
    group = store.current()
    return {"group": asdict(group) if group else None, "students": [asdict(s) for s in store.students()]}


@router.post("")
def create_group(body: GroupBody, engine: Engine = Depends(engine_dep)) -> dict:
    try:
        return asdict(GroupStore(engine).create(body.name, body.size))
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e


@router.put("")
def resize_group(body: ResizeBody, engine: Engine = Depends(engine_dep)) -> dict:
    store = GroupStore(engine)
    _group_or_404(store)
    try:
        return asdict(store.resize(body.size, body.name))
    except SeatsTaken as e:
        raise HTTPException(status_code=409, detail=str(e)) from e


@router.post("/students")
def add_student(body: StudentBody, engine: Engine = Depends(engine_dep)) -> dict:
    store = GroupStore(engine)
    _group_or_404(store)
    try:
        account, password = store.add_student(body.login, body.name, body.note)
    except GroupFull as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except LoginTaken as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    return {"student": asdict(store.student(account.id)), "password": password}


def _student_or_404(store: GroupStore, account_id: str):
    student = store.student(account_id)
    if student is None:
        raise HTTPException(status_code=404, detail="ученик не найден")
    return student


@router.put("/students/{account_id}")
def update_student(account_id: str, body: StudentUpdate, engine: Engine = Depends(engine_dep)) -> dict:
    store = GroupStore(engine)
    _student_or_404(store, account_id)
    store.update_student(account_id, note=body.note, budget_usd=body.budget_usd, name=body.name)
    return asdict(store.student(account_id))


@router.post("/students/{account_id}/password")
def reset_password(account_id: str, engine: Engine = Depends(engine_dep)) -> dict:
    _student_or_404(GroupStore(engine), account_id)
    password = login_password()
    AccountStore(engine).set_password(account_id, password)
    SessionStore(engine).close_all(account_id)  # старый пароль мог утечь — выходим со всех устройств
    return {"password": password}
