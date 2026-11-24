"""Работа ученика глазами преподавателя: вся переписка, команды и экран терминала, разбор задания, «почему не засчитано»."""
import base64

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import Engine

from apps.api.auth import teacher_dep
from apps.api.board import _student_or_404
from apps.api.deps import engine_dep, providers_dep, settings_dep
from apps.api.sandbox import manager_dep
from trainer.curriculum.tasks import TaskStore
from trainer.llm_gateway.gateway import GatewayError
from trainer.sandbox.manager import SandboxManager
from trainer.sandbox.termlog import TerminalLog
from trainer.settings import Settings
from trainer.tutor import review
from trainer.tutor.jobs import LlmDeps
from trainer.tutor.messages import MessageStore

router = APIRouter(prefix="/group/students/{student_id}", dependencies=[Depends(teacher_dep)])


def _task_or_404(engine: Engine, student_id: str, task_id: str):
    task = TaskStore(engine).get_for_student(task_id, student_id)
    if task is None:
        raise HTTPException(status_code=404, detail="задание не найдено")
    return task


@router.get("/chat")
def chat(student_id: str, task_id: str | None = None, engine: Engine = Depends(engine_dep)) -> list[dict]:
    _student_or_404(engine, student_id)
    if task_id is not None:
        _task_or_404(engine, student_id, task_id)
    return [{"at": m.created_at.isoformat(), "author": m.author, "agent": m.agent_key, "task_id": m.task_id,
             "task_title": title, "text": m.text, "model": m.meta.get("model"), "cost_usd": m.meta.get("cost_usd"),
             "reason": m.meta.get("reason")}
            for m, title in MessageStore(engine).student_chat(student_id, task_id)]


@router.get("/console")
def console(student_id: str, engine: Engine = Depends(engine_dep),
            manager: SandboxManager = Depends(manager_dep)) -> list[dict]:
    _student_or_404(engine, student_id)
    return review.console(manager, student_id)


@router.get("/terminal")
def terminal_screen(student_id: str, after: int = 0, engine: Engine = Depends(engine_dep)) -> dict:
    """Экран терминала: куски вывода (base64) и размеры окна после after; last — с чего продолжить опрос."""
    _student_or_404(engine, student_id)
    chunks = TerminalLog(engine).since(student_id, after)
    return {"chunks": [{"id": c.id, "kind": c.kind, "data": base64.b64encode(c.data).decode()} for c in chunks],
            "last": chunks[-1].id if chunks else after}


@router.get("/tasks/{task_id}/inspect")
def inspect(student_id: str, task_id: str, engine: Engine = Depends(engine_dep),
            manager: SandboxManager = Depends(manager_dep)) -> dict:
    return review.inspect(manager, _task_or_404(engine, student_id, task_id))


@router.post("/tasks/{task_id}/analyze")
def analyze(student_id: str, task_id: str, engine: Engine = Depends(engine_dep),
            settings: Settings = Depends(settings_dep), providers=Depends(providers_dep),
            manager: SandboxManager = Depends(manager_dep)) -> dict:
    task = _task_or_404(engine, student_id, task_id)
    try:
        return review.analyze(LlmDeps(engine, settings, providers), manager, task)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except GatewayError as e:
        raise HTTPException(status_code=502, detail=f"модель не ответила ({e.reason})") from e
