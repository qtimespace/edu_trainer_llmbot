"""Уроки и черновики заданий (только преподаватель)."""
from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import Engine

from apps.api.auth import teacher_dep
from apps.api.deps import engine_dep, providers_dep, runner_dep, settings_dep
from trainer.curriculum.lessons import LessonStore
from trainer.curriculum.methodist import prepare_lesson
from trainer.curriculum.tasks import Check, TaskStore
from trainer.settings import Settings
from trainer.tutor.jobs import LlmDeps

router = APIRouter(dependencies=[Depends(teacher_dep)])


class LessonBody(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=20000)


class LessonUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=20000)


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    statement: str | None = Field(default=None, max_length=10000)
    checks: list[Check] | None = Field(default=None, min_length=1, max_length=8)
    agent_key: str | None = None


class ApproveBody(BaseModel):
    student_id: str | None = None


def _lesson_or_404(engine: Engine, lesson_id: str):
    lesson = LessonStore(engine).get(lesson_id)
    if lesson is None:
        raise HTTPException(status_code=404, detail="урок не найден")
    return lesson


@router.get("/lessons")
def list_lessons(engine: Engine = Depends(engine_dep)) -> list[dict]:
    return [asdict(x) for x in LessonStore(engine).list()]


@router.post("/lessons")
def create_lesson(body: LessonBody, engine: Engine = Depends(engine_dep)) -> dict:
    try:
        return asdict(LessonStore(engine).create(body.title, body.description))
    except KeyError as e:
        raise HTTPException(status_code=409, detail="сначала создайте группу") from e


@router.put("/lessons/{lesson_id}")
def update_lesson(lesson_id: str, body: LessonUpdate, engine: Engine = Depends(engine_dep)) -> dict:
    lesson = LessonStore(engine).update(lesson_id, body.title, body.description)
    if lesson is None:
        raise HTTPException(status_code=404, detail="урок не найден")
    return asdict(lesson)


@router.get("/lessons/{lesson_id}/tasks")
def lesson_tasks(lesson_id: str, engine: Engine = Depends(engine_dep)) -> list[dict]:
    _lesson_or_404(engine, lesson_id)
    return [t.for_teacher() for t in TaskStore(engine).for_lesson(lesson_id)]


@router.post("/lessons/{lesson_id}/approve")
def approve_lesson(lesson_id: str, body: ApproveBody, engine: Engine = Depends(engine_dep)) -> dict:
    _lesson_or_404(engine, lesson_id)
    return {"approved": TaskStore(engine).approve_lesson(lesson_id, body.student_id)}


def _task_or_404(engine: Engine, task_id: str):
    task = TaskStore(engine).get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="задание не найдено")
    return task


@router.put("/tasks/{task_id}")
def update_task(task_id: str, body: TaskUpdate, engine: Engine = Depends(engine_dep)) -> dict:
    _task_or_404(engine, task_id)
    try:
        return TaskStore(engine).update(task_id, title=body.title, statement=body.statement, checks=body.checks,
                                        agent_key=body.agent_key).for_teacher()
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e


@router.post("/tasks/{task_id}/approve")
def approve_task(task_id: str, engine: Engine = Depends(engine_dep)) -> dict:
    _task_or_404(engine, task_id)
    try:
        return TaskStore(engine).approve(task_id).for_teacher()
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e


@router.delete("/tasks/{task_id}", status_code=204)
def delete_task(task_id: str, engine: Engine = Depends(engine_dep)) -> None:
    if not TaskStore(engine).delete(task_id):
        raise HTTPException(status_code=404, detail="задание не найдено")


class PrepareBody(BaseModel):
    student_id: str | None = None


@router.post("/lessons/{lesson_id}/prepare", status_code=202)
def prepare(lesson_id: str, body: PrepareBody, engine: Engine = Depends(engine_dep),
            settings: Settings = Depends(settings_dep), providers=Depends(providers_dep),
            run=Depends(runner_dep)) -> dict:
    _lesson_or_404(engine, lesson_id)
    if not LessonStore(engine).try_start_prep(lesson_id):
        raise HTTPException(status_code=409, detail="задания по уроку уже готовятся")
    run(prepare_lesson, LlmDeps(engine, settings, providers), lesson_id, body.student_id)
    return {"status": "running"}
