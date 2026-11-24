"""Сайт ученика: папку и публикацию задаёт преподаватель (по умолчанию выключено)."""
import os

import pytest
from fastapi.testclient import TestClient

from apps.api.main import app
from tests.helpers import PASS, login
from trainer import sites
from trainer.accounts.store import AccountStore
from trainer.classroom.groups import GroupStore


@pytest.fixture
def homes(api, database_url, tmp_path):
    """Дома учеников в tmp_path (как /srv/trainer/homes на сервере)."""
    from apps.api.deps import settings_dep
    from trainer.settings import Settings
    settings = Settings(_env_file=None, database_url=database_url, session_cookie_secure=False,
                        secrets_keys=os.environ["TRAINER_SECRETS_KEYS"], sandbox_backend="fake", homes_dir=tmp_path)
    app.dependency_overrides[settings_dep] = lambda: settings
    return tmp_path


@pytest.fixture
def kid(api, homes):
    AccountStore(api).create_account("anna", PASS, role="teacher")
    groups = GroupStore(api)
    groups.create("g", 2)
    account, _ = groups.add_student("kid1", "Петя")
    AccountStore(api).set_password(account.id, PASS)
    home = sites.home_of(homes, 1)
    (home / "site-maket").mkdir(parents=True)
    (home / "site-maket" / "index.html").write_text("<h1>Привет</h1>", encoding="utf-8")
    return account.id


def _client(user: str) -> TestClient:
    c = TestClient(app)
    login(c, user)
    return c


def test_site_is_off_by_default(kid):
    got = _client("anna").get(f"/group/students/{kid}/site").json()
    assert got == {"site_dir": None, "published": False, "suggested": "site-maket",
                   "url": "http://localhost:3000/s/kid1/"}


def test_teacher_sets_folder_and_publishes(kid, api):
    teacher = _client("anna")
    r = teacher.put(f"/group/students/{kid}/site", json={"site_dir": "site-maket", "published": True})
    assert r.status_code == 200 and r.json()["site_dir"] == "site-maket" and r.json()["published"] is True
    student = GroupStore(api).student(kid)
    assert (student.site_dir, student.site_published) == ("site-maket", True)


@pytest.mark.parametrize("bad", ["../x", ".ssh", "/etc", "a/../../b", "site/.git", "a//b", "x" * 201])
def test_bad_folder_rejected(kid, bad):
    r = _client("anna").put(f"/group/students/{kid}/site", json={"site_dir": bad, "published": False})
    assert r.status_code == 422


def test_publish_without_folder_409(kid):
    r = _client("anna").put(f"/group/students/{kid}/site", json={"site_dir": None, "published": True})
    assert r.status_code == 409


def test_suggest_finds_index(tmp_path):
    assert sites.suggest_dir(tmp_path) is None
    assert sites.suggest_dir(tmp_path / "нет") is None
    (tmp_path / ".hidden").mkdir()
    (tmp_path / ".hidden" / "index.html").write_text("x")
    (tmp_path / "work" / "site").mkdir(parents=True)
    (tmp_path / "work" / "site" / "index.html").write_text("x")
    assert sites.suggest_dir(tmp_path) == "work/site"
    (tmp_path / "site-maket").mkdir()
    (tmp_path / "site-maket" / "index.html").write_text("x")
    assert sites.suggest_dir(tmp_path) == "site-maket"


def test_valid_dir():
    assert sites.valid_dir("site-maket") and sites.valid_dir("work/my site") and sites.valid_dir("сайт")
    assert not sites.valid_dir("") and not sites.valid_dir(".ssh") and not sites.valid_dir("a/..")


def test_student_by_login_ignores_case(kid, api):
    assert GroupStore(api).student_by_login("KID1").account_id == kid
    assert GroupStore(api).student_by_login("nobody") is None


def test_student_cannot_touch_site_settings(kid):
    kid_client = _client("kid1")
    assert kid_client.get(f"/group/students/{kid}/site").status_code == 403
    assert kid_client.put(f"/group/students/{kid}/site", json={"site_dir": "x", "published": True}).status_code == 403
