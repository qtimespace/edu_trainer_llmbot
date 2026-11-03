"""Доска заданий ученика и перенос карточки между этапами флоу.

Перенос в рабочий этап — задание подхватывает агент этапа (ход тьютора). Перенос в «Готово» — только если прошли
все проверочные команды; иначе карточка остаётся, а агент этапа объясняет, что не так.
"""
from sqlalchemy import Engine, text

from trainer.agents.store import AgentStore
from trainer.curriculum.flow import DONE, START, Flow, FlowStore, agent_for, stage_of
from trainer.curriculum.tasks import Task, TaskStore
from trainer.sandbox.checks import run_checks
from trainer.sandbox.manager import SandboxManager

from .engine import tutor_turn
from .jobs import JobStore, LlmDeps
from .messages import MessageStore


class MoveError(Exception):
    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status, self.detail = status, detail


def tutor_keys(engine: Engine) -> set[str]:
    return {a.key for a in AgentStore(engine).list(kind="tutor", enabled_only=True)}


def board(engine: Engine, student_id: str) -> dict:
    flow, tutors = FlowStore(engine).get(), tutor_keys(engine)
    names = {a.key: a.name for a in AgentStore(engine).list()}
    with engine.connect() as c:
        lessons = {str(r.id): r.title for r in c.execute(text("SELECT id, title FROM lessons"))}
    running = {j.task_id for j in JobStore(engine).running(student_id)}
    agent = lambda key: {"key": key, "name": names.get(key, key)}  # noqa: E731
    return {
        "stages": [{"key": s.key, "name": s.name,
                    "agent": agent(s.agent_key) if s.agent_key in tutors else None} for s in flow.stages],
        "transitions": [list(t) for t in flow.transitions],
        "tasks": [{"id": t.id, "number": i + 1, "title": t.title, "lesson": lessons.get(t.lesson_id, ""),
                   "stage": stage_of(t, flow), "status": t.status, "running": t.id in running,
                   "agent": agent(agent_for(t, flow, tutors))}
                  for i, t in enumerate(TaskStore(engine).for_student(student_id))],
    }


def _names(flow: Flow, keys) -> str:
    return ", ".join(f"«{flow.stage(k).name}»" for k in keys)


def move_task(deps: LlmDeps, manager: SandboxManager, run, task: Task, target: str, *, by_teacher: bool) -> str:
    """Переносит задание на этап target; возвращает итоговый этап. Ошибка — MoveError (код HTTP и текст)."""
    engine = deps.engine
    flow, tasks, messages, jobs = FlowStore(engine).get(), TaskStore(engine), MessageStore(engine), JobStore(engine)
    current = stage_of(task, flow)
    if flow.stage(target) is None:
        raise MoveError(422, "нет такого этапа")
    if target == current:
        return current
    if by_teacher:
        if target == START or current == DONE:
            raise MoveError(409, "в «К выполнению» не возвращаем, из «Готово» не выносим")
    elif (current, target) not in flow.moves():
        allowed = [b for a, b in flow.transitions if a == current]
        raise MoveError(409, f"из «{flow.stage(current).name}» можно перенести только в {_names(flow, allowed)}"
                        if allowed else "это задание дальше не переносится")
    if jobs.is_running(task.id):
        raise MoveError(409, "агент ещё отвечает — подожди")
    if target == DONE:
        results = run_checks(manager, task.student_id, task.checks)
        if results and all(r.passed for r in results):
            tasks.set_status(task.id, "done")
            tasks.set_stage(task.id, DONE)
            messages.add(task.id, "system", "Все проверки прошли — задание готово.")
            return DONE
        failed = "; ".join(r.about for r in results if not r.passed) or "проверок нет"
        detail = f"В «Готово» пока рано — не прошли проверки: {failed}"
        messages.add(task.id, "system", detail)
        if task.status != "todo":
            _turn(deps, manager, run, task, current, flow)  # агент этапа разберёт, что не так
        raise MoveError(409, detail)
    _turn(deps, manager, run, task, target, flow, announce=current != START)
    return target


def _turn(deps: LlmDeps, manager: SandboxManager, run, task: Task, stage: str, flow: Flow, announce=False) -> None:
    engine = deps.engine
    tasks = TaskStore(engine)
    moved = Task(**{**task.__dict__, "stage": stage, "status": "in_progress"})
    agent_key = agent_for(moved, flow, tutor_keys(engine))
    job = JobStore(engine).start(agent_key, task_id=task.id, student_id=task.student_id)
    if job is None:
        raise MoveError(409, "агент уже отвечает по другому заданию — подожди")
    try:
        tasks.set_stage(task.id, stage)
        if task.status != "in_progress":
            tasks.set_status(task.id, "in_progress")
    except ValueError as e:
        JobStore(engine).finish(job, ok=False)
        raise MoveError(409, "задание изменилось одновременно — обнови доску") from e
    if announce:
        agent = AgentStore(engine).get(agent_key)
        MessageStore(engine).add(task.id, "system",
                                 f"Этап «{flow.stage(stage).name}» — дальше ведёт {agent.name if agent else agent_key}.")
    run(tutor_turn, deps, manager, task.id, task.student_id, job)
