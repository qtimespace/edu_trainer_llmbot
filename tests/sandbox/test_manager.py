import pytest
from fastapi.testclient import TestClient

from apps.api.main import app
from tests.helpers import PASS, login
from trainer.accounts.store import AccountStore
from trainer.classroom.groups import GroupStore
from trainer.sandbox.backend import FakeBackend
from trainer.sandbox.manager import SandboxManager, container_name, volume_name


@pytest.fixture
def world(api):
    fake = FakeBackend()
    import apps.api.sandbox as sandbox_api
    sandbox_api.BACKENDS["fake"] = fake
    AccountStore(api).create_account("anna", PASS, role="teacher")
    groups = GroupStore(api)
    groups.create("g", 2)
    kids = []
    for n in ("kid1", "kid2"):
        account, _ = groups.add_student(n, n)
        AccountStore(api).set_password(account.id, PASS)
        kids.append(account.id)
    return api, fake, kids


def test_ensure_passes_lesson_password(world):
    engine, fake, kids = world
    SandboxManager(fake, engine).ensure_for(kids[0])
    box = fake.boxes[container_name(kids[0])]
    assert box["env"]["LESSON_PASSWORD"] == GroupStore(engine).student(kids[0]).lesson_password
    assert box["volume"] == volume_name(kids[0])


def test_reset_wipes_volume_and_recreates(world):
    engine, fake, kids = world
    manager = SandboxManager(fake, engine)
    manager.ensure_for(kids[0])
    fake.volumes[volume_name(kids[0])]["file"] = "ученик всё сломал"
    manager.reset(kids[0])
    assert fake.status(container_name(kids[0])) == "running"
    assert fake.volumes[volume_name(kids[0])] == {}


def test_login_ensures_sandbox(world):
    engine, fake, kids = world
    login(TestClient(app), "kid1")
    assert fake.status(container_name(kids[0])) == "running"
    login(TestClient(app), "anna")  # у преподавателя песочницы нет
    assert len(fake.boxes) == 1


def test_student_resets_only_own(world):
    engine, fake, kids = world
    kid = TestClient(app)
    login(kid, "kid1")
    fake.volumes[volume_name(kids[0])]["file"] = "x"
    assert kid.post("/me/sandbox/reset").status_code == 204
    assert fake.volumes[volume_name(kids[0])] == {}
    assert kid.post(f"/group/students/{kids[1]}/sandbox/reset").status_code == 403


def test_teacher_resets_any_and_sees_status(world):
    engine, fake, kids = world
    teacher = TestClient(app)
    login(teacher, "anna")
    assert teacher.get(f"/group/students/{kids[1]}/sandbox").json() == {"status": "missing"}
    assert teacher.post(f"/group/students/{kids[1]}/sandbox/reset").status_code == 204
    assert teacher.get(f"/group/students/{kids[1]}/sandbox").json() == {"status": "running"}
    assert teacher.post("/group/students/not-a-kid/sandbox/reset").status_code == 404
