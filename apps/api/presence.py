from fastapi import APIRouter, Depends
from sqlalchemy import Engine

from apps.api import auth_local
from apps.api.auth import any_role_dep
from apps.api.deps import engine_dep
from trainer.classroom.presence import PresenceStore

router = APIRouter(prefix="/presence")


@router.post("/ping", status_code=204)
def ping(who=Depends(any_role_dep), engine: Engine = Depends(engine_dep)) -> None:
    PresenceStore(engine).ping(who.id)


auth_local.logout_hooks.append(lambda engine, account: PresenceStore(engine).drop(account.id))
