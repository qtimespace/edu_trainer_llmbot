"""Офис группы: комната на место; свет и агенты — только когда ученик в сети; что делает каждый агент."""
from sqlalchemy import Engine, text

from trainer.agents.store import AgentStore
from trainer.classroom.groups import GroupStore
from trainer.classroom.presence import PresenceStore
from trainer.curriculum.tasks import TaskStore
from trainer.tutor.jobs import JobStore


def _last_replies(engine: Engine, student_id: str) -> dict[str, str]:
    with engine.connect() as c:
        rows = c.execute(text("""SELECT DISTINCT ON (m.agent_key) m.agent_key, m.text
                                 FROM task_messages m JOIN tasks t ON t.id = m.task_id
                                 WHERE t.student_id = CAST(:s AS uuid) AND m.author = 'agent'
                                 ORDER BY m.agent_key, m.created_at DESC"""), {"s": student_id})
        return {r.agent_key: r.text for r in rows}


def _agent_state(agent_key: str, tasks: list, running_tasks: set[str]) -> tuple[str, object]:
    mine = [t for t in tasks if t.agent_key == agent_key]
    for t in mine:
        if t.id in running_tasks:
            return "typing", t
    for t in mine:
        if t.status == "waiting_student":
            return "waiting", t
    active = [t for t in mine if t.status == "in_progress"]
    if active:
        return "idle", active[0]
    done = [t for t in mine if t.status == "done"]
    if done and not any(t.status == "todo" for t in mine):
        return "done", done[-1]
    return "idle", None


def room_for(engine: Engine, student, online: bool, tutors) -> dict:
    room = {"seat": student.seat, "student": {"id": student.account_id, "name": student.name},
            "online": online, "lights": online, "agents": []}
    if not online:
        return room
    tasks = TaskStore(engine).for_student(student.account_id)
    running = {j.task_id for j in JobStore(engine).running(student.account_id) if j.task_id}
    replies = _last_replies(engine, student.account_id)
    for agent in tutors:
        state, task = _agent_state(agent.key, tasks, running)
        room["agents"].append({"key": agent.key, "name": agent.name, "state": state,
                               "task": {"id": task.id, "title": task.title, "status": task.status} if task else None,
                               "last_reply": replies.get(agent.key)})
    return room


def office(engine: Engine, only_student: str | None = None) -> dict:
    group = GroupStore(engine).current()
    if group is None:
        return {"size": 0, "rooms": []}
    students = {s.seat: s for s in GroupStore(engine).students()}
    online = PresenceStore(engine).online([s.account_id for s in students.values()])
    tutors = AgentStore(engine).list(kind="tutor", enabled_only=True)
    rooms = []
    for seat in range(1, group.size + 1):
        student = students.get(seat)
        if only_student is not None and (student is None or student.account_id != only_student):
            continue
        if student is None:
            rooms.append({"seat": seat, "student": None, "online": False, "lights": False, "agents": []})
        else:
            rooms.append(room_for(engine, student, student.account_id in online, tutors))
    return {"size": group.size, "rooms": rooms}
