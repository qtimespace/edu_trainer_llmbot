"""Доска заданий и флоу: ученик — своя доска и перенос по флоу; преподаватель — флоу и доска любого ученика."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import Engine

from apps.api.auth import student_dep, teacher_dep
from apps.api.deps import engine_dep, providers_dep, runner_dep, settings_dep
from apps.api.sandbox import manager_dep
from apps.api.tasks import own_task_or_404
from trainer.classroom.groups import GroupStore
from trainer.curriculum.flow import Flow, FlowStore
from trainer.curriculum.tasks import TaskStore
from trainer.sandbox.manager import SandboxManager
from trainer.settings import Settings
from trainer.tutor.board import MoveError, board, move_task, tutor_keys
from trainer.tutor.jobs import LlmDeps

router = APIRouter()


class MoveBody(BaseModel):
    stage: str = Field(min_length=1, max_length=32)


def _move(engine, settings, providers, run, manager, task, stage: str, by_teacher: bool) -> dict:
    try:
        return {"stage": move_task(LlmDeps(engine, settings, providers), manager, run, task, stage, by_teacher=by_teacher)}
    except MoveError as e:
        raise HTTPException(status_code=e.status, detail=e.detail) from e


@router.get("/me/board")
def my_board(who=Depends(student_dep), engine: Engine = Depends(engine_dep)) -> dict:
    return board(engine, who.id)


@router.post("/me/tasks/{task_id}/move", status_code=202)
def move_mine(task_id: str, body: MoveBody, who=Depends(student_dep), engine: Engine = Depends(engine_dep),
              settings: Settings = Depends(settings_dep), providers=Depends(providers_dep), run=Depends(runner_dep),
              manager: SandboxManager = Depends(manager_dep)) -> dict:
    task = own_task_or_404(engine, task_id, who.id)
    return _move(engine, settings, providers, run, manager, task, body.stage, by_teacher=False)


def _student_or_404(engine: Engine, student_id: str) -> None:
    if GroupStore(engine).student(student_id) is None:
        raise HTTPException(status_code=404, detail="ученик не найден")


@router.get("/group/students/{student_id}/board", dependencies=[Depends(teacher_dep)])
def student_board(student_id: str, engine: Engine = Depends(engine_dep)) -> dict:
    _student_or_404(engine, student_id)
    return board(engine, student_id)


@router.post("/group/students/{student_id}/tasks/{task_id}/move", status_code=202, dependencies=[Depends(teacher_dep)])
def move_for_student(student_id: str, task_id: str, body: MoveBody, engine: Engine = Depends(engine_dep),
                     settings: Settings = Depends(settings_dep), providers=Depends(providers_dep),
                     run=Depends(runner_dep), manager: SandboxManager = Depends(manager_dep)) -> dict:
    task = TaskStore(engine).get_for_student(task_id, student_id)
    if task is None:
        raise HTTPException(status_code=404, detail="задание не найдено")
    return _move(engine, settings, providers, run, manager, task, body.stage, by_teacher=True)


@router.get("/flow", dependencies=[Depends(teacher_dep)])
def get_flow(engine: Engine = Depends(engine_dep)) -> dict:
    return FlowStore(engine).get().model_dump()


@router.put("/flow", dependencies=[Depends(teacher_dep)])
def put_flow(body: Flow, engine: Engine = Depends(engine_dep)) -> dict:
    tutors = tutor_keys(engine)
    for s in body.stages:
        if s.agent_key is not None and s.agent_key not in tutors:
            raise HTTPException(status_code=422, detail=f"этап «{s.name}»: агент {s.agent_key} — не включённый тьютор")
    return FlowStore(engine).save(body).model_dump()
