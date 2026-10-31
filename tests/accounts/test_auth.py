import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from apps.api import auth as auth_mod
from apps.api.main import app
from tests.helpers import PASS, login
from trainer.accounts.seed import seed_teacher
from trainer.accounts.store import AccountStore


@pytest.fixture
def client(api):
    return TestClient(app), AccountStore(api)


def test_login_sets_cookie_and_me(client):
    c, accounts = client
    accounts.create_account("ivan", PASS, name="Иван", role="student")
    r = c.post("/auth/login", json={"login": "ivan", "password": PASS})
    assert r.status_code == 200 and "trainer_session" in r.cookies and r.json()["csrf"]
    me = c.get("/auth/me").json()
    assert me["account"]["name"] == "Иван" and me["account"]["role"] == "student"


def test_wrong_password_401_and_throttle_429(client):
    c, accounts = client
    accounts.create_account("ivan", PASS, role="student")
    bad = c.post("/auth/login", json={"login": "ivan", "password": "wrong password!"})
    unknown = c.post("/auth/login", json={"login": "nobody", "password": "wrong password!"})
    assert bad.status_code == unknown.status_code == 401 and bad.json() == unknown.json()
    for _ in range(9):
        c.post("/auth/login", json={"login": "ivan", "password": "wrong password!"})
    assert c.post("/auth/login", json={"login": "ivan", "password": PASS}).status_code == 429


def test_post_without_csrf_403(client):
    c, accounts = client
    accounts.create_account("ivan", PASS, role="student")
    login(c, "ivan")
    del c.headers["X-CSRF-Token"]
    assert c.post("/auth/logout").status_code == 403


def test_change_password_is_throttled(client):
    c, accounts = client
    accounts.create_account("ivan", PASS, role="student")
    login(c, "ivan")
    for _ in range(10):
        assert c.post("/auth/password", json={"old": "wrong password!", "new": "brand new password"}).status_code == 403
    assert c.post("/auth/password", json={"old": PASS, "new": "brand new password"}).status_code == 429


def test_teacher_dep_rejects_student(client):
    _, accounts = client
    accounts.create_account("ivan", PASS, role="student")
    accounts.create_account("anna", PASS, role="teacher")
    probe = FastAPI()
    probe.dependency_overrides = app.dependency_overrides
    probe.include_router(__import__("apps.api.auth_local", fromlist=["router"]).router)

    @probe.get("/probe")
    def _probe(who=Depends(auth_mod.teacher_dep)):
        return {"login": who.login}

    student, teacher = TestClient(probe), TestClient(probe)
    login(student, "ivan")
    login(teacher, "anna")
    assert student.get("/probe").status_code == 403
    assert teacher.get("/probe").json() == {"login": "anna"}
    assert TestClient(probe).get("/probe").status_code == 401


def test_seed_teacher_from_env(api):
    accounts = AccountStore(api)
    assert seed_teacher(accounts, "anna", PASS) == "created"
    assert accounts.by_login("anna").role == "teacher"
    assert seed_teacher(accounts, "anna", PASS) == "unchanged"
    assert seed_teacher(accounts, "anna", "short") == "weak"
