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
from trainer.curriculum.tasks import Check, TaskStore
from trainer.llm_gateway.errors import ProviderError
from trainer.sandbox.backend import ExecResult, FakeBackend
from trainer.tutor.jobs import JobStore

CHECKS = [Check(cmd="test -f ~/Temp/test.py", about="в Temp есть test.py"),
          Check(cmd="test ! -d ~/Tmp", about="папки Tmp больше нет")]


@pytest.fixture
def world(api):
    """Ученики kid1, kid2; у каждого одобренное задание с двумя проверками; песочница — заглушка."""
    import apps.api.sandbox as sandbox_api
    passing = {"test -f ~/Temp/test.py": True, "test ! -d ~/Tmp": True}
    history = {"/home/student/.bash_history": "#1700000100\nmkdir Temp\n"}

    def handler(name, cmd, user):
        if cmd[0] == "tail":
            return ExecResult(0, history.get(cmd[-1], ""))
        return ExecResult(0 if passing.get(cmd[-1]) else 1, "")
    fake = FakeBackend(handler)
    sandbox_api.BACKENDS["fake"] = fake
    seed_agents(AgentStore(api))
    add_model(api)
    groups = GroupStore(api)
    groups.create("g", 2)
    kids = []
    for n in ("kid1", "kid2"):
        account, _ = groups.add_student(n, n)
        AccountStore(api).set_password(account.id, PASS)
        kids.append(account.id)
    lesson = LessonStore(api).create("Bash", "")
    tasks = TaskStore(api)
    ids = []
    for kid in kids:
        t = tasks.create_draft(lesson.id, kid, "devops", "Папка Temp", "Удали Tmp, создай Temp/test.py", CHECKS)
        tasks.approve(t.id)
        ids.append(t.id)
    c = TestClient(app)
    login(c, "kid1")
    return api, c, kids, ids, passing


def _status(engine, task_id):
    return TaskStore(engine).get(task_id).status


def test_start_asks_first_question(world):
    engine, kid, kids, ids, passing = world
    passing["test -f ~/Temp/test.py"] = False
    fake = install_fake_llm(app, [reply({"reply": "Как подключишься к серверу?", "done": False})])
    assert kid.post(f"/me/tasks/{ids[0]}/start").status_code == 202
    msgs = kid.get(f"/me/tasks/{ids[0]}/messages").json()
    assert msgs["running"] is False and msgs["status"] == "waiting_student"
    assert [m["text"] for m in msgs["messages"]] == ["Как подключишься к серверу?"]
    assert "Удали Tmp" in fake.calls[0].user and "mkdir Temp" in fake.calls[0].user
    assert "✗ в Temp есть test.py" in fake.calls[0].user


def test_done_only_when_all_checks_pass(world):
    engine, kid, kids, ids, passing = world
    passing["test ! -d ~/Tmp"] = False
    install_fake_llm(app, [reply({"reply": "Отлично!", "done": True})])
    kid.post(f"/me/tasks/{ids[0]}/start")
    assert _status(engine, ids[0]) == "waiting_student"


def test_all_checks_pass_closes_task(world):
    engine, kid, kids, ids, passing = world
    install_fake_llm(app, [reply({"reply": "Как дела?", "done": False}), reply({"reply": "Готово!", "done": False})])
    passing["test -f ~/Temp/test.py"] = False
    kid.post(f"/me/tasks/{ids[0]}/start")
    passing["test -f ~/Temp/test.py"] = True
    assert kid.post(f"/me/tasks/{ids[0]}/messages", json={"text": "сделал"}).status_code == 202
    msgs = kid.get(f"/me/tasks/{ids[0]}/messages").json()
    assert msgs["status"] == "done" and [m["author"] for m in msgs["messages"]] == ["agent", "student", "agent"]
    assert kid.post(f"/me/tasks/{ids[0]}/messages", json={"text": "ещё"}).status_code == 409


def test_checks_cmd_not_leaked_to_student_messages(world):
    engine, kid, kids, ids, passing = world
    install_fake_llm(app, [reply({"reply": "Смотри, test -f ~/Temp/test.py — не скажу", "done": False})])
    passing["test -f ~/Temp/test.py"] = False
    kid.post(f"/me/tasks/{ids[0]}/start")
    body = kid.get(f"/me/tasks/{ids[0]}/messages").json()
    agent = body["messages"][0]
    assert agent["checks"] == [{"about": "в Temp есть test.py", "passed": False},
                               {"about": "папки Tmp больше нет", "passed": True}]
    assert "cmd" not in str(agent["checks"]) and "model" not in agent and "cost_usd" not in agent


def test_tutor_garbage_reply_is_soft_error(world):
    engine, kid, kids, ids, passing = world
    passing["test -f ~/Temp/test.py"] = False
    install_fake_llm(app, [reply("я не умею в JSON")])
    kid.post(f"/me/tasks/{ids[0]}/start")
    msgs = kid.get(f"/me/tasks/{ids[0]}/messages").json()
    assert msgs["status"] == "waiting_student" and msgs["messages"][0]["author"] == "system"
    assert "попробуй ещё раз" in msgs["messages"][0]["text"]
    assert JobStore(engine).running() == []


def test_provider_down_is_soft_error(world):
    engine, kid, kids, ids, passing = world
    passing["test -f ~/Temp/test.py"] = False
    install_fake_llm(app, [ProviderError("quota_exceeded", "402"), ProviderError("quota_exceeded", "402")])
    kid.post(f"/me/tasks/{ids[0]}/start")
    assert kid.get(f"/me/tasks/{ids[0]}/messages").json()["messages"][0]["author"] == "system"


def test_budget_exhausted_message(world):
    engine, kid, kids, ids, passing = world
    GroupStore(engine).update_student(kids[0], budget_usd=0)
    fake = install_fake_llm(app, [])
    kid.post(f"/me/tasks/{ids[0]}/start")
    msgs = kid.get(f"/me/tasks/{ids[0]}/messages").json()
    assert fake.calls == [] and "Лимит" in msgs["messages"][0]["text"]


def test_second_message_while_running_is_409(world):
    engine, kid, kids, ids, passing = world
    install_fake_llm(app, [])
    TaskStore(engine).set_status(ids[0], "in_progress")
    JobStore(engine).start("devops", task_id=ids[0], student_id=kids[0])
    assert kid.post(f"/me/tasks/{ids[0]}/messages", json={"text": "ау"}).status_code == 409
    assert kid.get(f"/me/tasks/{ids[0]}/messages").json()["running"] is True


def test_student_cannot_post_to_foreign_task(world):
    engine, kid, kids, ids, passing = world
    install_fake_llm(app, [])
    assert kid.post(f"/me/tasks/{ids[1]}/start").status_code == 404
    assert kid.post(f"/me/tasks/{ids[1]}/messages", json={"text": "x"}).status_code == 404
    assert kid.get(f"/me/tasks/{ids[1]}/messages").status_code == 404


def test_tiny_budget_left_is_no_budget_not_retry(world):
    engine, kid, kids, ids, passing = world
    passing["test -f ~/Temp/test.py"] = False
    GroupStore(engine).update_student(kids[0], budget_usd=0.0005)
    fake = install_fake_llm(app, [])
    kid.post(f"/me/tasks/{ids[0]}/start")
    msg = kid.get(f"/me/tasks/{ids[0]}/messages").json()["messages"][0]
    assert fake.calls == [] and "Лимит" in msg["text"] and "на сегодня" not in msg["text"]


def test_teacher_key_out_of_money_is_explained(world, api):
    engine, kid, kids, ids, passing = world
    passing["test -f ~/Temp/test.py"] = False
    install_fake_llm(app, [ProviderError("quota_exceeded", "402")] * 3)
    kid.post(f"/me/tasks/{ids[0]}/start")
    msg = kid.get(f"/me/tasks/{ids[0]}/messages").json()["messages"][0]
    assert "преподавател" in msg["text"]
    teacher = TestClient(app)
    AccountStore(api).create_account("anna", PASS, role="teacher")
    login(teacher, "anna")
    feed = teacher.get(f"/office/rooms/{kids[0]}/feed").json()
    assert feed[0]["reason"] == "quota_exceeded"


def test_one_turn_per_student_across_tasks(world):
    engine, kid, kids, ids, passing = world
    tasks = TaskStore(engine)
    lesson = tasks.get(ids[0]).lesson_id
    other = tasks.create_draft(lesson, kids[0], "devops", "Второе", "", CHECKS)
    tasks.approve(other.id)
    install_fake_llm(app, [])
    tasks.set_status(ids[0], "in_progress")
    JobStore(engine).start("devops", task_id=ids[0], student_id=kids[0])
    assert kid.post(f"/me/tasks/{other.id}/start").status_code == 409
    assert tasks.get(other.id).status == "todo"


def test_stale_running_job_does_not_block_forever(world):
    engine, kid, kids, ids, passing = world
    from sqlalchemy import text
    passing["test -f ~/Temp/test.py"] = False
    install_fake_llm(app, [reply({"reply": "Снова привет", "done": False})])
    tasks = TaskStore(engine)
    tasks.set_status(ids[0], "in_progress")
    tasks.set_status(ids[0], "waiting_student")
    JobStore(engine).start("devops", task_id=ids[0], student_id=kids[0])
    with engine.begin() as c:
        c.execute(text("UPDATE agent_jobs SET started_at = now() - interval '10 minutes'"))
    assert kid.post(f"/me/tasks/{ids[0]}/messages", json={"text": "ау"}).status_code == 202


def test_long_history_lines_are_capped(world):
    from trainer.tutor.engine import _prompt
    engine, kid, kids, ids, passing = world
    task = TaskStore(engine).get(ids[0])
    prompt = _prompt(task, [], ["student$ echo " + "x" * 50000] * 40, [])
    assert len(prompt) < 20000
