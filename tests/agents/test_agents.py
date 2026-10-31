import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from apps.api.main import app
from tests.helpers import PASS, login
from trainer.accounts.store import AccountStore
from trainer.agents.seed import seed_agents
from trainer.agents.store import AgentStore


def test_seed_creates_methodist_and_devops_once(engine):
    store = AgentStore(engine)
    assert seed_agents(store) == ["methodist", "devops"]
    store.upsert(store.get("devops").model_copy(update={"name": "Мой Девопс"}))
    assert seed_agents(store) == []
    assert store.get("devops").name == "Мой Девопс"  # сид не перезаписывает правки преподавателя
    assert [a.key for a in store.list(kind="tutor")] == ["devops"]
    assert "JSON" in store.get("methodist").system_prompt


@pytest.fixture
def client(api):
    accounts = AccountStore(api)
    accounts.create_account("anna", PASS, role="teacher")
    accounts.create_account("kid", PASS, role="student")
    seed_agents(AgentStore(api))
    return api


def test_student_cannot_list_agents_403(client):
    kid = TestClient(app)
    login(kid, "kid")
    assert kid.get("/agents").status_code == 403


def test_teacher_edits_agent(client):
    t = TestClient(app)
    login(t, "anna")
    body = {"name": "Сисадмин", "kind": "tutor", "system_prompt": "Ты сисадмин", "route": ["openrouter/m"],
            "max_usd_per_call": 0.02, "enabled": True}
    assert t.put("/agents/sysadmin", json=body).status_code == 200
    assert {a["key"] for a in t.get("/agents").json()} == {"methodist", "devops", "sysadmin"}


def test_delete_referenced_agent_409(client):
    engine = client
    with engine.begin() as c:
        g = c.execute(text("INSERT INTO groups (name, size) VALUES ('g', 2) RETURNING id")).scalar_one()
        lesson = c.execute(text("INSERT INTO lessons (group_id, title) VALUES (:g, 'l') RETURNING id"),
                           {"g": g}).scalar_one()
        kid = c.execute(text("SELECT id FROM accounts WHERE login = 'kid'")).scalar_one()
        c.execute(text("INSERT INTO tasks (lesson_id, student_id, agent_key, title) VALUES (:l, :k, 'devops', 't')"),
                  {"l": lesson, "k": kid})
    t = TestClient(app)
    login(t, "anna")
    assert t.delete("/agents/devops").status_code == 409
    assert t.delete("/agents/methodist").status_code == 204
