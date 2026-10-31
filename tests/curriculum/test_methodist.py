import pytest
from fastapi.testclient import TestClient

from apps.api.main import app
from tests.fakes import add_model, install_fake_llm, reply
from tests.helpers import PASS, login
from trainer.accounts.store import AccountStore
from trainer.agents.seed import seed_agents
from trainer.agents.store import AgentStore
from trainer.classroom.groups import GroupStore
from trainer.curriculum.lessons import LessonStore
from trainer.curriculum.tasks import TaskStore

TASKS = {"tasks": [
    {"title": "Подключись", "statement": "Подключись к lab", "agent_key": "devops",
     "checks": [{"cmd": "grep -q 'ssh student@lab' /home/lobby/.bash_history", "about": "была команда ssh"}]},
    {"title": "Папка Temp", "statement": "Создай Temp и test.py", "agent_key": "nobody",
     "checks": [{"cmd": "test -f ~/Temp/test.py", "about": "есть Temp/test.py"}]},
]}


@pytest.fixture
def world(api):
    AccountStore(api).create_account("anna", PASS, role="teacher")
    seed_agents(AgentStore(api))
    add_model(api)
    groups = GroupStore(api)
    groups.create("g", 2)
    kids = [groups.add_student(n, n, note="новичок")[0].id for n in ("kid1", "kid2")]
    lesson = LessonStore(api).create("Bash", "ssh, ls, cd, touch, rm")
    teacher = TestClient(app)
    login(teacher, "anna")
    return api, teacher, kids, lesson


def test_prepare_creates_drafts_per_student(world):
    engine, teacher, kids, lesson = world
    fake = install_fake_llm(app, [reply(TASKS), reply("```json\n" + __import__("json").dumps(TASKS) + "\n```")])
    assert teacher.post(f"/lessons/{lesson.id}/prepare", json={}).status_code == 202
    tasks = TaskStore(engine).for_lesson(lesson.id)
    assert len(tasks) == 4 and {t.status for t in tasks} == {"draft"}
    assert {t.student_id for t in tasks} == set(kids)
    assert "новичок" in fake.calls[0].user and "ssh, ls" in fake.calls[0].user and "devops" in fake.calls[0].user
    assert LessonStore(engine).get(lesson.id).prep_status == "idle"


def test_unknown_agent_key_falls_back_to_tutor(world):
    engine, teacher, kids, lesson = world
    install_fake_llm(app, [reply(TASKS), reply(TASKS)])
    teacher.post(f"/lessons/{lesson.id}/prepare", json={})
    assert {t.agent_key for t in TaskStore(engine).for_lesson(lesson.id)} == {"devops"}


def test_invalid_json_sets_prep_error(world):
    engine, teacher, kids, lesson = world
    install_fake_llm(app, [reply("извините, не могу"), reply({"tasks": []})])
    teacher.post(f"/lessons/{lesson.id}/prepare", json={})
    got = LessonStore(engine).get(lesson.id)
    assert got.prep_status == "failed" and "kid1" in got.prep_error and "kid2" in got.prep_error
    assert TaskStore(engine).for_lesson(lesson.id) == []


def test_prepare_one_student(world):
    engine, teacher, kids, lesson = world
    fake = install_fake_llm(app, [reply(TASKS)])
    teacher.post(f"/lessons/{lesson.id}/prepare", json={"student_id": kids[1]})
    assert len(fake.calls) == 1 and {t.student_id for t in TaskStore(engine).for_lesson(lesson.id)} == {kids[1]}


def test_prepare_twice_409(world):
    engine, teacher, kids, lesson = world
    install_fake_llm(app, [])
    LessonStore(engine).set_prep(lesson.id, "running")
    assert teacher.post(f"/lessons/{lesson.id}/prepare", json={}).status_code == 409
