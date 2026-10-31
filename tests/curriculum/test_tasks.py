import pytest
from fastapi.testclient import TestClient

from apps.api.main import app
from tests.helpers import PASS, login
from trainer.accounts.store import AccountStore
from trainer.agents.seed import seed_agents
from trainer.agents.store import AgentStore
from trainer.classroom.groups import GroupStore
from trainer.curriculum.lessons import LessonStore
from trainer.curriculum.tasks import Check, TaskStore


@pytest.fixture
def world(api):
    """Преподаватель, группа на 2, два ученика (kid1, kid2), урок, по черновику на ученика."""
    AccountStore(api).create_account("anna", PASS, role="teacher")
    seed_agents(AgentStore(api))
    groups = GroupStore(api)
    groups.create("g", 2)
    kids = []
    for login_ in ("kid1", "kid2"):
        account, _ = groups.add_student(login_, login_)
        AccountStore(api).set_password(account.id, PASS)
        kids.append(account.id)
    lesson = LessonStore(api).create("Bash", "ls, cd, touch")
    tasks = TaskStore(api)
    drafts = [tasks.create_draft(lesson.id, kid, "devops", f"Задание {kid[:4]}", "Создай файл",
                                 [Check(cmd="test -f ~/a.txt", about="файл a.txt есть")]) for kid in kids]
    return api, kids, lesson, drafts


def _client(user):
    c = TestClient(app)
    login(c, user)
    return c


def test_student_never_sees_draft(world):
    engine, kids, lesson, drafts = world
    kid = _client("kid1")
    assert kid.get("/me/tasks").json() == []
    assert kid.get(f"/me/tasks/{drafts[0].id}").status_code == 404
    TaskStore(engine).approve(drafts[0].id)
    assert [t["id"] for t in kid.get("/me/tasks").json()] == [drafts[0].id]


def test_student_cannot_read_foreign_task(world):
    engine, kids, lesson, drafts = world
    TaskStore(engine).approve_lesson(lesson.id)
    kid = _client("kid1")
    assert kid.get(f"/me/tasks/{drafts[1].id}").status_code == 404
    assert kid.get("/me/tasks/not-a-uuid").status_code == 404


def test_student_payload_has_no_checks(world):
    engine, kids, lesson, drafts = world
    TaskStore(engine).approve(drafts[0].id)
    kid = _client("kid1")
    one = kid.get(f"/me/tasks/{drafts[0].id}").json()
    assert "checks" not in one and "checks" not in kid.get("/me/tasks").json()[0]
    assert "test -f" not in kid.get("/me/tasks").text


def test_invalid_transition_raises(world):
    engine, kids, lesson, drafts = world
    tasks = TaskStore(engine)
    with pytest.raises(ValueError):
        tasks.set_status(drafts[0].id, "done")
    tasks.approve(drafts[0].id)
    tasks.set_status(drafts[0].id, "in_progress")
    tasks.set_status(drafts[0].id, "waiting_student")
    tasks.set_status(drafts[0].id, "done")
    with pytest.raises(ValueError):
        tasks.set_status(drafts[0].id, "in_progress")


def test_approve_lesson_only_drafts(world):
    engine, kids, lesson, drafts = world
    teacher = _client("anna")
    assert teacher.post(f"/lessons/{lesson.id}/approve", json={"student_id": kids[0]}).status_code == 200
    statuses = {t["student_id"]: t["status"] for t in teacher.get(f"/lessons/{lesson.id}/tasks").json()}
    assert statuses == {kids[0]: "todo", kids[1]: "draft"}


def test_teacher_edits_draft_and_creates_lesson(world):
    engine, kids, lesson, drafts = world
    teacher = _client("anna")
    r = teacher.put(f"/tasks/{drafts[0].id}", json={"title": "Новое", "checks": [{"cmd": "true", "about": "ok"}]})
    assert r.status_code == 200 and r.json()["title"] == "Новое" and r.json()["checks"][0]["cmd"] == "true"
    created = teacher.post("/lessons", json={"title": "Git", "description": "init, commit"}).json()
    assert [x["title"] for x in teacher.get("/lessons").json()] == ["Bash", "Git"] and created["prep_status"] == "idle"
    assert _client("kid1").get("/lessons").status_code == 403
