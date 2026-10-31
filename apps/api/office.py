"""Офис: преподаватель видит все комнаты и ленту ответов LLM по комнате; ученик — только свою комнату."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import Engine

from apps.api.auth import any_role_dep, teacher_dep
from apps.api.deps import engine_dep
from trainer.classroom.groups import GroupStore
from trainer.office import office as build_office
from trainer.tutor.messages import MessageStore

router = APIRouter(prefix="/office")


@router.get("")
def get_office(who=Depends(any_role_dep), engine: Engine = Depends(engine_dep)) -> dict:
    if who.role == "teacher":
        return build_office(engine)
    return build_office(engine, only_student=who.id)


@router.get("/rooms/{student_id}/feed", dependencies=[Depends(teacher_dep)])
def feed(student_id: str, engine: Engine = Depends(engine_dep)) -> list[dict]:
    if GroupStore(engine).student(student_id) is None:
        raise HTTPException(status_code=404, detail="ученик не найден")
    return [{"at": m.created_at.isoformat(), "author": m.author, "agent": m.agent_key, "task_title": title,
             "text": m.text, "model": m.meta.get("model"), "cost_usd": m.meta.get("cost_usd"),
             "checks": m.meta.get("checks", [])}
            for m, title in MessageStore(engine).agent_feed(student_id)]
