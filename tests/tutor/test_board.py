"""Доска ученика: колонки — этапы флоу преподавателя; перенос по разрешённым переходам; «Готово» — только по проверкам."""
from fastapi.testclient import TestClient

from apps.api.main import app
from tests.fakes import install_fake_llm, reply
from tests.helpers import PASS, login
from tests.tutor.test_api import world  # noqa: F401 — фикстура
from trainer.accounts.store import AccountStore
from trainer.curriculum.tasks import TaskStore
from trainer.tutor.messages import MessageStore

ASK = reply({"reply": "С чего начнёшь?", "done": False})


def _teacher(engine) -> TestClient:
    c = TestClient(app)
    AccountStore(engine).create_account("anna", PASS, role="teacher")
    login(c, "anna")
    return c


def _card(board, task_id):
    return next(t for t in board["tasks"] if t["id"] == task_id)


def test_board_shows_flow_columns_and_own_tasks_only(world):
    engine, kid, kids, ids, passing = world
    board = kid.get("/me/board").json()
    assert [s["name"] for s in board["stages"]] == ["К выполнению", "Анализ", "Разработка", "Ревью", "Готово"]
    assert board["stages"][1]["agent"] == {"key": "sa", "name": "Системный аналитик"}
    assert ["review", "done"] in board["transitions"]
    assert [t["id"] for t in board["tasks"]] == [ids[0]]
    card = board["tasks"][0]
    assert card == {"id": ids[0], "number": 1, "title": "Папка Temp", "lesson": "Bash", "stage": "todo",
                    "status": "todo", "running": False, "agent": {"key": "devops", "name": "Девопс"}}


def test_moving_to_the_next_stage_hands_the_task_to_its_agent(world):
    engine, kid, kids, ids, passing = world
    passing["test -f ~/Temp/test.py"] = False
    fake = install_fake_llm(app, [ASK, reply({"reply": "Покажи решение", "done": False})])
    assert kid.post(f"/me/tasks/{ids[0]}/move", json={"stage": "analysis"}).status_code == 202
    assert "Системный аналитик" in fake.calls[0].system or "системный аналитик" in fake.calls[0].system
    assert "Анализ" in fake.calls[0].user
    card = _card(kid.get("/me/board").json(), ids[0])
    assert card["stage"] == "analysis" and card["status"] == "waiting_student" and card["agent"]["key"] == "sa"
    assert kid.post(f"/me/tasks/{ids[0]}/move", json={"stage": "dev"}).status_code == 202
    texts = [m.text for m in MessageStore(engine).for_task(ids[0])]
    assert any("Разработка" in t and "Девопс" in t for t in texts)  # отметка смены этапа в чате
    assert _card(kid.get("/me/board").json(), ids[0])["agent"]["key"] == "devops"


def test_student_moves_only_along_the_flow(world):
    engine, kid, kids, ids, passing = world
    install_fake_llm(app, [ASK])
    r = kid.post(f"/me/tasks/{ids[0]}/move", json={"stage": "review"})
    assert r.status_code == 409 and "Анализ" in r.json()["detail"]
    assert kid.post(f"/me/tasks/{ids[0]}/move", json={"stage": "nope"}).status_code == 422
    assert kid.post(f"/me/tasks/{ids[1]}/move", json={"stage": "analysis"}).status_code == 404
    assert _card(kid.get("/me/board").json(), ids[0])["stage"] == "todo"


def test_done_only_when_checks_pass_otherwise_agent_explains(world):
    engine, kid, kids, ids, passing = world
    passing["test ! -d ~/Tmp"] = False
    fake = install_fake_llm(app, [ASK, ASK, ASK, reply({"reply": "Папка Tmp ещё на месте", "done": False})])
    for stage in ("analysis", "dev", "review"):
        kid.post(f"/me/tasks/{ids[0]}/move", json={"stage": stage})
    r = kid.post(f"/me/tasks/{ids[0]}/move", json={"stage": "done"})
    assert r.status_code == 409 and "папки Tmp больше нет" in r.json()["detail"]
    assert len(fake.calls) == 4  # агент этапа объясняет, что не так
    assert _card(kid.get("/me/board").json(), ids[0])["stage"] == "review"
    passing["test ! -d ~/Tmp"] = True
    assert kid.post(f"/me/tasks/{ids[0]}/move", json={"stage": "done"}).status_code == 202
    card = _card(kid.get("/me/board").json(), ids[0])
    assert card["stage"] == "done" and card["status"] == "done"


def test_tutor_closes_the_task_only_on_a_stage_that_leads_to_done(world):
    engine, kid, kids, ids, passing = world
    install_fake_llm(app, [ASK, ASK])
    kid.post(f"/me/tasks/{ids[0]}/move", json={"stage": "analysis"})  # все проверки уже проходят
    assert TaskStore(engine).get(ids[0]).status == "waiting_student"
    TaskStore(engine).set_stage(ids[0], "review")
    kid.post(f"/me/tasks/{ids[0]}/messages", json={"text": "готово"})
    assert TaskStore(engine).get(ids[0]).status == "done"


def test_teacher_sees_student_board_and_moves_anywhere_but_back_to_todo(world):
    engine, kid, kids, ids, passing = world
    passing["test -f ~/Temp/test.py"] = False
    install_fake_llm(app, [ASK])
    teacher = _teacher(engine)
    assert _card(teacher.get(f"/group/students/{kids[1]}/board").json(), ids[1])["stage"] == "todo"
    assert teacher.post(f"/group/students/{kids[1]}/tasks/{ids[1]}/move", json={"stage": "review"}).status_code == 202
    assert TaskStore(engine).get(ids[1]).stage == "review"
    assert teacher.post(f"/group/students/{kids[1]}/tasks/{ids[1]}/move", json={"stage": "todo"}).status_code == 409
    assert teacher.post(f"/group/students/{kids[0]}/tasks/{ids[1]}/move", json={"stage": "dev"}).status_code == 404
    assert kid.get(f"/group/students/{kids[0]}/board").status_code == 403


def test_teacher_edits_the_flow(world):
    engine, kid, kids, ids, passing = world
    teacher = _teacher(engine)
    flow = teacher.get("/flow").json()
    assert flow["stages"][0]["key"] == "todo"
    mine = {"stages": [{"key": "todo", "name": "Очередь", "agent_key": None},
                       {"key": "code", "name": "Код", "agent_key": "python"},
                       {"key": "done", "name": "Готово", "agent_key": None}],
            "transitions": [["todo", "code"], ["code", "done"]]}
    assert teacher.put("/flow", json={**mine, "transitions": [["todo", "code"]]}).status_code == 422
    bad_agent = {**mine, "stages": [mine["stages"][0], {**mine["stages"][1], "agent_key": "methodist"}, mine["stages"][2]]}
    assert teacher.put("/flow", json=bad_agent).status_code == 422  # вести этап может только тьютор
    assert teacher.put("/flow", json=mine).status_code == 200
    assert [s["name"] for s in kid.get("/me/board").json()["stages"]] == ["Очередь", "Код", "Готово"]
    assert kid.put("/flow", json=mine).status_code == 403
