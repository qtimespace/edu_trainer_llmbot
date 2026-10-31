"""Песочницы: пересоздание (ученик — свою, преподаватель — любую), статус; подъём при входе ученика."""
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import Engine

from apps.api import auth_local
from apps.api.auth import student_dep, teacher_dep
from apps.api.deps import engine_dep, settings_dep
from trainer.sandbox.backend import FakeBackend, SandboxBackend
from trainer.sandbox.manager import NoSandbox, SandboxManager
from trainer.settings import Settings

log = logging.getLogger(__name__)
router = APIRouter()
BACKENDS: dict[str, SandboxBackend] = {}  # один бэкенд на процесс; тесты подкладывают свой FakeBackend


def get_backend(settings: Settings) -> SandboxBackend:
    kind = settings.sandbox_backend
    if kind not in BACKENDS:
        if kind == "fake":
            BACKENDS[kind] = FakeBackend()
        else:
            from trainer.sandbox.docker_backend import DockerBackend
            BACKENDS[kind] = DockerBackend(settings)
    return BACKENDS[kind]


def manager_dep(engine: Engine = Depends(engine_dep), settings: Settings = Depends(settings_dep)) -> SandboxManager:
    return SandboxManager(get_backend(settings), engine)


@router.post("/me/sandbox/reset", status_code=204)
def reset_mine(who=Depends(student_dep), manager: SandboxManager = Depends(manager_dep)) -> None:
    try:
        manager.reset(who.id)
    except NoSandbox as e:
        raise HTTPException(status_code=404, detail="вы не в группе") from e


@router.post("/group/students/{student_id}/sandbox/reset", status_code=204, dependencies=[Depends(teacher_dep)])
def reset_student(student_id: str, manager: SandboxManager = Depends(manager_dep)) -> None:
    try:
        manager.reset(student_id)
    except NoSandbox as e:
        raise HTTPException(status_code=404, detail="ученик не найден") from e


@router.get("/group/students/{student_id}/sandbox", dependencies=[Depends(teacher_dep)])
def sandbox_status(student_id: str, manager: SandboxManager = Depends(manager_dep)) -> dict:
    try:
        return {"status": manager.status(student_id)}
    except NoSandbox as e:
        raise HTTPException(status_code=404, detail="ученик не найден") from e


def _ensure_on_login(engine: Engine, settings: Settings, account) -> None:
    if account.role != "student":
        return
    try:
        SandboxManager(get_backend(settings), engine).ensure_for(account.id)
    except NoSandbox:
        pass
    except Exception:  # noqa: BLE001 — вход не должен падать из-за Docker; терминал поднимет песочницу сам
        log.exception("песочница %s не поднялась при входе", account.login)


auth_local.login_hooks.append(_ensure_on_login)
