import pytest
from fastapi.testclient import TestClient

from apps.api.main import app
from tests.helpers import PASS, login
from trainer.accounts.store import AccountStore
from trainer.classroom.groups import GroupStore


@pytest.fixture
def teacher(api):
    AccountStore(api).create_account("anna", PASS, role="teacher")
    c = TestClient(app)
    login(c, "anna")
    return c


@pytest.mark.parametrize("size,code", [(1, 422), (2, 200), (5, 200), (6, 422)])
def test_create_group_size_2_to_5(teacher, size, code):
    assert teacher.post("/group", json={"name": "Пятница", "size": size}).status_code == code


def test_add_student_takes_next_seat(teacher, api):
    teacher.post("/group", json={"name": "g", "size": 3})
    r1 = teacher.post("/group/students", json={"login": "kid1", "name": "Петя", "note": "видел Linux"})
    r2 = teacher.post("/group/students", json={"login": "kid2", "name": "Маша"})
    assert r1.status_code == r2.status_code == 200
    assert [r1.json()["student"]["seat"], r2.json()["student"]["seat"]] == [1, 2]
    pwd = r1.json()["password"]
    assert len(pwd) >= 12 and AccountStore(api).check_password("kid1", pwd) is not None
    students = teacher.get("/group").json()["students"]
    assert students[0]["note"] == "видел Linux" and students[0]["lesson_password"]
    assert "password" not in students[0]


def test_add_beyond_size_409(teacher):
    teacher.post("/group", json={"name": "g", "size": 2})
    for i in range(2):
        teacher.post("/group/students", json={"login": f"kid{i}", "name": "x"})
    assert teacher.post("/group/students", json={"login": "kid9", "name": "x"}).status_code == 409


def test_resize_below_occupied_409(teacher, api):
    teacher.post("/group", json={"name": "g", "size": 4})
    for i in range(3):
        teacher.post("/group/students", json={"login": f"kid{i}", "name": "x"})
    assert teacher.put("/group", json={"size": 2}).status_code == 409
    assert teacher.put("/group", json={"size": 3}).status_code == 200
    assert GroupStore(api).current().size == 3


def test_student_cannot_call_group_api_403(teacher, api):
    teacher.post("/group", json={"name": "g", "size": 2})
    teacher.post("/group/students", json={"login": "kid1", "name": "x"})
    AccountStore(api).set_password(AccountStore(api).by_login("kid1").id, PASS)
    kid = TestClient(app)
    login(kid, "kid1")
    assert kid.get("/group").status_code == 403
    assert kid.post("/group/students", json={"login": "evil", "name": "x"}).status_code == 403
