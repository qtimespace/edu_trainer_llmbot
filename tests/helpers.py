"""Общие помощники API-тестов: приложение с подменёнными зависимостями и вход."""
from fastapi.testclient import TestClient

PASS = "correct horse battery"


def const(value):
    return lambda: value


def login(c: TestClient, user: str, password: str = PASS):
    r = c.post("/auth/login", json={"login": user, "password": password})
    assert r.status_code == 200, r.text
    c.headers["X-CSRF-Token"] = r.json()["csrf"]
    return r
