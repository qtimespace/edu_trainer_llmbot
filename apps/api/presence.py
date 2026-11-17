from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import Engine

from apps.api import auth_local
from apps.api.auth import any_role_dep, teacher_dep
from apps.api.deps import engine_dep
from trainer.classroom.groups import GroupStore
from trainer.classroom.presence import PresenceStore, State

router = APIRouter()


class PingBody(BaseModel):
    state: State | None = None  # куда смотрит вкладка ученика; у преподавателя не передаётся


@router.post("/presence/ping", status_code=204)
def ping(body: PingBody | None = Body(default=None), who=Depends(any_role_dep),
         engine: Engine = Depends(engine_dep)) -> None:
    PresenceStore(engine).ping(who.id, state=body.state if body and who.role == "student" else None)


@router.get("/group/students/{student_id}/attention", dependencies=[Depends(teacher_dep)])
def attention(student_id: str, since: datetime | None = None, engine: Engine = Depends(engine_dep)) -> dict:
    """Внимание ученика с `since` (панель передаёт начало дня по своим часам); без него — последние 12 часов."""
    if GroupStore(engine).student(student_id) is None:
        raise HTTPException(status_code=404, detail="ученик не найден")
    since = since or datetime.now(UTC) - timedelta(hours=12)
    return PresenceStore(engine).attention(student_id, since if since.tzinfo else since.replace(tzinfo=UTC))


auth_local.logout_hooks.append(lambda engine, account: PresenceStore(engine).drop(account.id))
