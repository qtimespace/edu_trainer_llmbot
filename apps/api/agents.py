"""Агенты (только преподаватель)."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import Engine

from apps.api.auth import teacher_dep
from apps.api.deps import engine_dep
from trainer.agents.store import Agent, AgentInUse, AgentStore, Kind

router = APIRouter(prefix="/agents", dependencies=[Depends(teacher_dep)])


class AgentBody(BaseModel):
    name: str
    kind: Kind
    system_prompt: str = ""
    route: list[str] = []
    max_usd_per_call: float = 0.05
    enabled: bool = True


@router.get("")
def list_agents(engine: Engine = Depends(engine_dep)) -> list[dict]:
    return [a.model_dump() for a in AgentStore(engine).list()]


@router.put("/{key}")
def save_agent(key: str, body: AgentBody, engine: Engine = Depends(engine_dep)) -> dict:
    try:
        agent = Agent(key=key, **body.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return AgentStore(engine).upsert(agent).model_dump()


@router.delete("/{key}", status_code=204)
def delete_agent(key: str, engine: Engine = Depends(engine_dep)) -> None:
    try:
        found = AgentStore(engine).delete(key)
    except AgentInUse as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    if not found:
        raise HTTPException(status_code=404, detail="агент не найден")
