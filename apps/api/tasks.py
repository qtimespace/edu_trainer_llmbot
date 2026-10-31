"""Задания ученика: только свои, только одобренные, без проверочных команд."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import Engine

from apps.api.auth import student_dep
from apps.api.deps import engine_dep
from trainer.curriculum.tasks import TaskStore

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
