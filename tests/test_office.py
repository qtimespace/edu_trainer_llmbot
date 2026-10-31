import pytest
from fastapi.testclient import TestClient

from apps.api.main import app
from tests.helpers import PASS, login
from trainer.accounts.store import AccountStore
from trainer.agents.seed import seed_agents
from trainer.agents.store import Agent, AgentStore
from trainer.classroom.groups import GroupStore
from trainer.classroom.presence import PresenceStore
from trainer.curriculum.lessons import LessonStore
from trainer.curriculum.tasks import Check, TaskStore
from trainer.tutor.jobs import JobStore
from trainer.tutor.messages import MessageStore


@pytest.fixture
def world(api):
    AccountStore(api).create_account("anna", PASS, role="teacher")
    seed_agents(AgentStore(api))
    AgentStore(api).upsert(Agent(key="pythonist", name="Питонист", kind="tutor"))
    groups = GroupStore(api)
    groups.create("g", 3)
    kids = []
    for n in ("kid1", "kid2"):
        account, _ = groups.add_student(n, n)
        AccountStore(api).set_password(account.id, PASS)
        kids.append(account.id)
    lesson = LessonStore(api).create("Bash", "")
    task = TaskStore(api).create_draft(lesson.id, kids[0], "devops", "Папка Temp", "", [Check(cmd="true")])
    TaskStore(api).approve(task.id)
    teacher = TestClient(app)
    login(teacher, "anna")
    return api, teacher, kids, task


def _room(office, seat):
    return next(r for r in office["rooms"] if r["seat"] == seat)


def test_offline_room_dark_and_empty(world):
    engine, teacher, kids, task = world
    office = teacher.get("/office").json()
    assert office["size"] == 3 and [r["seat"] for r in office["rooms"]] == [1, 2, 3]
    room = _room(office, 2)
    assert room["student"]["name"] == "kid2" and room["online"] is False and room["lights"] is False
    assert room["agents"] == []
    assert _room(office, 3)["student"] is None


def test_online_room_has_tutors(world):
    engine, teacher, kids, task = world
    PresenceStore(engine).ping(kids[0])
    room = _room(teacher.get("/office").json(), 1)
    assert room["lights"] is True
    assert {a["key"]: a["state"] for a in room["agents"]} == {"devops": "idle", "pythonist": "idle"}


def test_typing_state_while_job_running(world):
    engine, teacher, kids, task = world
    PresenceStore(engine).ping(kids[0])
    TaskStore(engine).set_status(task.id, "in_progress")
    JobStore(engine).start("devops", task_id=task.id, student_id=kids[0])
    devops = next(a for a in _room(teacher.get("/office").json(), 1)["agents"] if a["key"] == "devops")
    assert devops["state"] == "typing" and devops["task"]["title"] == "Папка Temp"


def test_waiting_state_shows_last_reply(world):
    engine, teacher, kids, task = world
    PresenceStore(engine).ping(kids[0])
    TaskStore(engine).set_status(task.id, "in_progress")
    TaskStore(engine).set_status(task.id, "waiting_student")
    MessageStore(engine).add(task.id, "agent", "Как подключишься?", agent_key="devops")
    devops = next(a for a in _room(teacher.get("/office").json(), 1)["agents"] if a["key"] == "devops")
    assert devops["state"] == "waiting" and devops["last_reply"] == "Как подключишься?"


def test_student_sees_only_own_room(world):
    engine, teacher, kids, task = world
    kid = TestClient(app)
    login(kid, "kid2")
    office = kid.get("/office").json()
    assert [r["seat"] for r in office["rooms"]] == [2]


def test_feed_teacher_only(world):
    engine, teacher, kids, task = world
    MessageStore(engine).add(task.id, "student", "секрет ученика")
    MessageStore(engine).add(task.id, "agent", "Привет!", agent_key="devops", meta={"model": "openrouter/m",
                                                                                   "cost_usd": 0.001})
    feed = teacher.get(f"/office/rooms/{kids[0]}/feed").json()
    assert [(f["agent"], f["text"], f["model"], f["task_title"]) for f in feed] == \
        [("devops", "Привет!", "openrouter/m", "Папка Temp")]
    kid = TestClient(app)
    login(kid, "kid1")
    assert kid.get(f"/office/rooms/{kids[0]}/feed").status_code == 403
