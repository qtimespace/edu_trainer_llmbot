"""Задания ученика: только свои, только одобренные, без проверочных команд; ходы агента по заданию."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import Engine

from apps.api.auth import student_dep
from apps.api.deps import engine_dep, providers_dep, runner_dep, settings_dep
from apps.api.sandbox import manager_dep
from trainer.curriculum.tasks import TaskStore
from trainer.sandbox.manager import SandboxManager
from trainer.settings import Settings
from trainer.tutor.engine import tutor_turn
from trainer.tutor.jobs import JobStore, LlmDeps
from trainer.tutor.messages import MessageStore

router = APIRouter(prefix="/me/tasks")


def own_task_or_404(engine: Engine, task_id: str, student_id: str):
    task = TaskStore(engine).get_for_student(task_id, student_id)
    if task is None:
        raise HTTPException(status_code=404, detail="задание не найдено")
    return task


@router.get("")
def my_tasks(who=Depends(student_dep), engine: Engine = Depends(engine_dep)) -> list[dict]:
    return [t.for_student() for t in TaskStore(engine).for_student(who.id)]


@router.get("/{task_id}")
def my_task(task_id: str, who=Depends(student_dep), engine: Engine = Depends(engine_dep)) -> dict:
    return own_task_or_404(engine, task_id, who.id).for_student()


@router.get("/{task_id}/messages")
def messages(task_id: str, who=Depends(student_dep), engine: Engine = Depends(engine_dep)) -> dict:
    task = own_task_or_404(engine, task_id, who.id)
    return {"status": task.status, "running": JobStore(engine).is_running(task_id),
            "messages": [m.for_student() for m in MessageStore(engine).for_task(task_id)]}


class MessageBody(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


def _lock(engine: Engine, task, student_id: str) -> str:
    """Ход агента: один на задание и один на ученика (параллельные ходы не превышают лимит расходов)."""
    job = JobStore(engine).start(task.agent_key, task_id=task.id, student_id=student_id)
    if job is None:
        raise HTTPException(status_code=409, detail="агент ещё отвечает — подожди")
    return job


@router.post("/{task_id}/start", status_code=202)
def start(task_id: str, who=Depends(student_dep), engine: Engine = Depends(engine_dep),
          settings: Settings = Depends(settings_dep), providers=Depends(providers_dep), run=Depends(runner_dep),
          manager: SandboxManager = Depends(manager_dep)) -> dict:
    task = own_task_or_404(engine, task_id, who.id)
    if task.status != "todo":
        raise HTTPException(status_code=409, detail="задание уже начато")
    job = _lock(engine, task, who.id)
    try:
        TaskStore(engine).set_status(task_id, "in_progress")
    except ValueError as e:  # параллельный «старт» успел раньше
        JobStore(engine).finish(job, ok=False)
        raise HTTPException(status_code=409, detail="задание уже начато") from e
    run(tutor_turn, LlmDeps(engine, settings, providers), manager, task.id, who.id, job)
    return {"status": "running"}


@router.post("/{task_id}/messages", status_code=202)
def send(task_id: str, body: MessageBody, who=Depends(student_dep), engine: Engine = Depends(engine_dep),
         settings: Settings = Depends(settings_dep), providers=Depends(providers_dep), run=Depends(runner_dep),
         manager: SandboxManager = Depends(manager_dep)) -> dict:
    task = own_task_or_404(engine, task_id, who.id)
    if task.status in ("todo", "done"):
        raise HTTPException(status_code=409, detail="задание не в работе")
    if JobStore(engine).is_running(task_id):
        raise HTTPException(status_code=409, detail="агент ещё отвечает — подожди")
    MessageStore(engine).add(task_id, "student", body.text.strip())
    if task.status == "waiting_student":
        job = _lock(engine, task, who.id)
    try:
        TaskStore(engine).set_status(task_id, "in_progress")
    except ValueError as e:  # параллельный «старт» успел раньше
        JobStore(engine).finish(job, ok=False)
        raise HTTPException(status_code=409, detail="задание уже начато") from e
    run(tutor_turn, LlmDeps(engine, settings, providers), manager, task.id, who.id, job)
    return {"status": "running"}
