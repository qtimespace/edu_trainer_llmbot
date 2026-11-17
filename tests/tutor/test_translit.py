"""Нет русской раскладки: ученик пишет транслитом, агент переводит в кириллицу — текст можно вставить в файл или чат."""
from fastapi.testclient import TestClient

from apps.api.main import app
from tests.fakes import install_fake_llm, reply
from tests.helpers import PASS, login
from tests.tutor.test_api import world  # noqa: F401 — фикстура
from trainer.accounts.store import AccountStore
from trainer.classroom.groups import GroupStore
from trainer.llm.wiring import spent_usd
from trainer.llm_gateway.errors import ProviderError


def test_translit_becomes_russian_and_is_paid_from_the_students_budget(world):
    engine, kid, kids, ids, passing = world
    fake = install_fake_llm(app, [reply("Привет, мир! Мой файл: idea.txt")])
    r = kid.post(f"/me/tasks/{ids[0]}/translit", json={"text": "Privet, mir! Moj fajl: idea.txt"})
    assert r.status_code == 200 and r.json() == {"text": "Привет, мир! Мой файл: idea.txt"}
    call = fake.calls[0]
    assert "Privet, mir! Moj fajl: idea.txt" in call.user
    assert "транслит" in call.system.lower()
    assert spent_usd(engine, kids[0]) > 0  # расход — на ученика, как ходы тьютора


def test_translit_answer_is_cleaned_of_quotes_and_code_fences(world):
    engine, kid, kids, ids, passing = world
    install_fake_llm(app, [reply("```\nПривет\nпока\n```"), reply("«Привет»")])
    assert kid.post(f"/me/tasks/{ids[0]}/translit", json={"text": "privet\npoka"}).json()["text"] == "Привет\nпока"
    assert kid.post(f"/me/tasks/{ids[0]}/translit", json={"text": "privet"}).json()["text"] == "Привет"


def test_translit_only_for_own_task_and_sane_text(world):
    engine, kid, kids, ids, passing = world
    install_fake_llm(app, [])
    assert kid.post(f"/me/tasks/{ids[1]}/translit", json={"text": "privet"}).status_code == 404  # чужое задание
    assert kid.post(f"/me/tasks/{ids[0]}/translit", json={"text": "   "}).status_code == 422
    assert kid.post(f"/me/tasks/{ids[0]}/translit", json={"text": "a" * 2001}).status_code == 422
    teacher = TestClient(app)
    AccountStore(engine).create_account("anna", PASS, role="teacher")
    login(teacher, "anna")
    assert teacher.post(f"/me/tasks/{ids[0]}/translit", json={"text": "privet"}).status_code == 403


def test_translit_without_budget_or_model_says_so(world):
    engine, kid, kids, ids, passing = world
    install_fake_llm(app, [ProviderError("provider_error")])
    r = kid.post(f"/me/tasks/{ids[0]}/translit", json={"text": "privet"})
    assert r.status_code == 502 and "не ответ" in r.json()["detail"]
    GroupStore(engine).update_student(kids[0], budget_usd=0)
    r = kid.post(f"/me/tasks/{ids[0]}/translit", json={"text": "privet"})
    assert r.status_code == 409 and "Лимит" in r.json()["detail"]
