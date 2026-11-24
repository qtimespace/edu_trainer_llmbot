"""Сайт ученика в интернете: /s/<логин>/ — только статика из его папки, отрезанная от панели (CSP sandbox)."""
import os

import pytest
from fastapi.testclient import TestClient

from apps.api.main import app
from tests.classroom.test_sites_settings import _client, homes, kid  # noqa: F401 — фикстуры
from trainer import sites
from trainer.classroom.groups import GroupStore

CSP = "sandbox allow-scripts allow-forms allow-popups allow-modals"


@pytest.fixture
def site(kid, homes, api):
    root = sites.home_of(homes, 1) / "site-maket"
    (root / "css").mkdir()
    (root / "css" / "style.css").write_text("h1{color:red}", encoding="utf-8")
    (root / "о сайте.html").write_text("<p>я</p>", encoding="utf-8")
    GroupStore(api).set_site(kid, "site-maket", True)
    return root


def _web() -> TestClient:
    return TestClient(app, follow_redirects=False)


def test_published_site_serves_index_and_files(site):
    r = _web().get("/s/kid1/")
    assert r.status_code == 200 and "Привет" in r.text and r.headers["content-type"].startswith("text/html")
    r = _web().get("/s/kid1/css/style.css")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/css") and r.text == "h1{color:red}"
    assert _web().get("/s/kid1/css/").status_code == 404  # каталог без index.html — списка файлов нет


def test_unpublished_is_404(kid):
    assert _web().get("/s/kid1/").status_code == 404
    assert _web().get("/s/nobody/").status_code == 404


def test_turning_off_is_immediate(site, kid, api):
    assert _web().get("/s/kid1/").status_code == 200
    GroupStore(api).set_site(kid, "site-maket", False)
    assert _web().get("/s/kid1/").status_code == 404


def test_login_case_insensitive(site):
    assert _web().get("/s/KID1/").status_code == 200


def test_no_slash_redirects(site):
    r = _web().get("/s/kid1")
    assert r.status_code == 307 and r.headers["location"] == "/s/kid1/"


@pytest.mark.parametrize("path", [".bash_history", "../.bash_history", "%2e%2e/.bash_history", "css/../../x",
                                  ".git/config", "css//style.css"])
def test_hidden_and_dotdot_404(site, homes, path):
    home = sites.home_of(homes, 1)
    (home / ".bash_history").write_text("секрет")
    (site / ".bash_history").write_text("секрет")
    # «../» клиент склеивает сам (уходит на /s/.bash_history → 307 → 404) — главное, что файла нет
    r = TestClient(app).get(f"/s/kid1/{path}")
    assert r.status_code == 404 and "секрет" not in r.text


def test_symlink_outside_folder_404(site, homes, kid, api):
    home = sites.home_of(homes, 1)
    (home / "секрет.txt").write_text("секрет")
    try:
        (site / "link.txt").symlink_to(home / "секрет.txt")
    except OSError:
        pytest.skip("нет прав на ярлыки (Windows без режима разработчика)")
    assert _web().get("/s/kid1/link.txt").status_code == 404
    other = sites.home_of(homes, 2) / "site"
    other.mkdir(parents=True)
    (other / "index.html").write_text("чужой")
    (home / "stolen").symlink_to(other, target_is_directory=True)
    GroupStore(api).set_site(kid, "stolen", True)
    r = _web().get("/s/kid1/")
    assert r.status_code == 404 and "чужой" not in r.text


def test_unknown_type_and_big_file_404(site):
    (site / "run.sh").write_text("echo hi")
    (site / "big.png").write_bytes(b"0" * (sites.MAX_BYTES + 1))
    assert _web().get("/s/kid1/run.sh").status_code == 404
    assert _web().get("/s/kid1/big.png").status_code == 404


def test_cyrillic_filename_served(site):
    r = _web().get("/s/kid1/%D0%BE%20%D1%81%D0%B0%D0%B9%D1%82%D0%B5.html")
    assert r.status_code == 200 and r.text == "<p>я</p>"


def test_security_headers_on_every_answer(site):
    for path in ("/s/kid1/", "/s/kid1/nope.html", "/s/nobody/"):
        h = _web().get(path).headers
        assert h["content-security-policy"] == CSP and h["x-content-type-options"] == "nosniff"
        assert h["cache-control"] == "no-cache"


def test_student_sees_own_site_url(site, kid, api):
    assert _client("kid1").get("/me/site").json() == {"url": "http://localhost:3000/s/kid1/"}
    GroupStore(api).set_site(kid, "site-maket", False)
    assert _client("kid1").get("/me/site").json() == {"url": None}


def test_file_swapped_for_symlink_after_the_check_is_not_served(site, homes, monkeypatch):
    """Гонка: проверили обычный файл, а к открытию ученик подменил его ярлыком на чужой дом — не отдаём."""
    other = sites.home_of(homes, 2)
    other.mkdir(parents=True)
    (other / "id_ed25519").write_text("чужой ключ")
    (site / "a.txt").write_text("обычный файл")
    try:
        (site / "probe").symlink_to(other / "id_ed25519")
        (site / "probe").unlink()
    except OSError:
        pytest.skip("нет прав на ярлыки (Windows без режима разработчика)")
    checked = sites.resolve

    def swap_after_check(*a):
        target = checked(*a)
        if target is not None and target.name == "a.txt":
            target.unlink()
            target.symlink_to(other / "id_ed25519")
        return target

    monkeypatch.setattr(sites, "resolve", swap_after_check)
    r = TestClient(app).get("/s/kid1/a.txt")
    assert r.status_code == 404 and "чужой" not in r.text


def test_fifo_is_not_served(site):
    if not hasattr(os, "mkfifo"):
        pytest.skip("нет mkfifo")
    os.mkfifo(site / "pipe.txt")
    assert TestClient(app).get("/s/kid1/pipe.txt").status_code == 404


def test_site_folder_swapped_for_symlink_after_the_check_is_not_served(site, homes, monkeypatch):
    """Гонка на уровне папки: после проверки ученик подменил саму папку сайта ярлыком на чужой дом."""
    other = sites.home_of(homes, 2) / "site"
    other.mkdir(parents=True)
    (other / "index.html").write_text("чужой сайт")
    try:
        (site.parent / "probe").symlink_to(other, target_is_directory=True)
        (site.parent / "probe").unlink()
    except OSError:
        pytest.skip("нет прав на ярлыки (Windows без режима разработчика)")
    checked = sites.resolve

    def swap_after_check(*a):
        target = checked(*a)
        if target is not None:
            site.rename(site.parent / "old-site")
            site.symlink_to(other, target_is_directory=True)
        return target

    monkeypatch.setattr(sites, "resolve", swap_after_check)
    r = TestClient(app).get("/s/kid1/index.html")
    assert r.status_code == 404 and "чужой" not in r.text
