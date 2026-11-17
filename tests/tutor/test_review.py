"""Преподаватель смотрит работу ученика: переписка, команды в терминале, разбор задания и «почему не засчитано»."""
from fastapi.testclient import TestClient

from apps.api.main import app
from tests.fakes import install_fake_llm, reply
from tests.helpers import PASS, login
from tests.tutor.test_api import world  # noqa: F401 — фикстура
from trainer.accounts.store import AccountStore


def _teacher(engine) -> TestClient:
    c = TestClient(app)
    AccountStore(engine).create_account("anna", PASS, role="teacher")
    login(c, "anna")
    return c


def test_teacher_sees_the_whole_chat_including_student_messages(world):
    engine, kid, kids, ids, passing = world
    install_fake_llm(app, [reply({"reply": "С чего начнёшь?", "done": False}),
                           reply({"reply": "Посмотри на имя папки", "done": False})])
    kid.post(f"/me/tasks/{ids[0]}/start")
    kid.post(f"/me/tasks/{ids[0]}/messages", json={"text": "а чем писать в файл?"})
    teacher = _teacher(engine)
    chat = teacher.get(f"/group/students/{kids[0]}/chat").json()
    assert [(m["author"], m["text"]) for m in chat] == [
        ("agent", "С чего начнёшь?"), ("student", "а чем писать в файл?"), ("agent", "Посмотри на имя папки")]
    assert chat[0]["task_title"] == "Папка Temp" and chat[0]["task_id"] == ids[0]
    assert len(teacher.get(f"/group/students/{kids[0]}/chat", params={"task_id": ids[0]}).json()) == 3
    assert teacher.get(f"/group/students/{kids[0]}/chat", params={"task_id": ids[1]}).status_code == 404  # чужое
    assert kid.get(f"/group/students/{kids[0]}/chat").status_code == 403  # ученику — нельзя


def test_teacher_sees_the_terminal_commands_with_time_and_shell(world):
    engine, kid, kids, ids, passing = world
    console = _teacher(engine).get(f"/group/students/{kids[0]}/console").json()
    assert console == [{"at": 1700000100, "where": "student", "cmd": "mkdir Temp"}]


def test_inspect_shows_check_commands_outputs_and_suspicious_files(world):
    engine, kid, kids, ids, passing = world
    passing["test ! -d ~/Tmp"] = False
    got = _teacher(engine).get(f"/group/students/{kids[0]}/tasks/{ids[0]}/inspect").json()
    assert [(c["cmd"], c["passed"]) for c in got["checks"]] == [("test -f ~/Temp/test.py", True),
                                                                ("test ! -d ~/Tmp", False)]
    files = {f["path"]: f["note"] for f in got["files"]}
    assert files["~/Temp/test.py"] == ""
    assert "похож" in files["~/temp"] and "похож" in files["~/Temp"]  # две папки, разница только в регистре
    assert "вход" in files["/home/lobby/idea.txt"]  # создал до ssh — не на сервере lab


def test_why_not_done_asks_the_model_for_a_teacher_facing_analysis(world):
    engine, kid, kids, ids, passing = world
    passing["test ! -d ~/Tmp"] = False
    fake = install_fake_llm(app, [reply("Ученик не удалил Tmp; подскажите про rm -r.")])
    r = _teacher(engine).post(f"/group/students/{kids[0]}/tasks/{ids[0]}/analyze")
    assert r.status_code == 200 and r.json()["text"] == "Ученик не удалил Tmp; подскажите про rm -r."
    user = fake.calls[0].user
    assert "test ! -d ~/Tmp" in user and "✗" in user  # видит сами проверочные команды
    assert "~/temp" in user and "mkdir Temp" in user  # файлы и команды ученика
    assert kid.post(f"/group/students/{kids[0]}/tasks/{ids[0]}/analyze").status_code == 403


def test_inspect_of_a_foreign_task_is_404(world):
    engine, kid, kids, ids, passing = world
    assert _teacher(engine).get(f"/group/students/{kids[0]}/tasks/{ids[1]}/inspect").status_code == 404
