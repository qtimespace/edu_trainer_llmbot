import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from apps.api.main import app
from tests.helpers import PASS, login
from trainer.accounts.store import AccountStore
from trainer.llm.keys import LlmKeyStore
from trainer.llm.wiring import secret_box


def test_key_roundtrip_encrypted(engine):
    store = LlmKeyStore(engine, secret_box())
    store.set("openrouter", "sk-or-very-secret")
    with engine.connect() as c:
        raw = c.execute(text("SELECT secret FROM llm_keys WHERE provider = 'openrouter'")).scalar_one()
    assert raw.startswith("enc:v1:") and "very-secret" not in raw
    assert store.get("openrouter") == "sk-or-very-secret"
    assert store.status() == {**{"openrouter": False, "hf": False, "zai": False, "kimi": False, "anthropic": False}, "openrouter": True}
    with pytest.raises(ValueError):
        store.set("openai", "x")


@pytest.fixture
def teacher(api):
    AccountStore(api).create_account("anna", PASS, role="teacher")
    c = TestClient(app)
    login(c, "anna")
    return c


def test_settings_never_returns_key(teacher):
    assert teacher.put("/settings/llm/keys/hf", json={"key": "hf_super_secret"}).status_code == 204
    body = teacher.get("/settings/llm").text
    assert "hf_super_secret" not in body
    assert teacher.get("/settings/llm").json()["keys"] == {**{"openrouter": False, "hf": False, "zai": False, "kimi": False, "anthropic": False}, "hf": True}
    assert teacher.delete("/settings/llm/keys/hf").status_code == 204
    assert teacher.get("/settings/llm").json()["keys"]["hf"] is False


def test_student_cannot_touch_llm_settings(api):
    AccountStore(api).create_account("kid", PASS, role="student")
    c = TestClient(app)
    login(c, "kid")
    assert c.get("/settings/llm").status_code == 403
    assert c.put("/settings/llm/keys/hf", json={"key": "x"}).status_code == 403


def test_teacher_adds_model_to_catalog(teacher):
    body = {"provider": "openrouter", "model": "qwen/qwen3-coder", "capabilities": ["reasoning"],
            "context_window": 128000, "pricing": {"input": 0.2, "output": 0.8}}
    assert teacher.put("/settings/llm/models/openrouter/qwen3-coder", json=body).status_code == 200
    keys = [m["key"] for m in teacher.get("/settings/llm").json()["models"]]
    assert keys == ["openrouter/qwen3-coder"]
    assert teacher.delete("/settings/llm/models/openrouter/qwen3-coder").status_code == 204


@pytest.mark.parametrize("provider", ["zai", "kimi", "anthropic"])
def test_direct_providers_take_a_key(teacher, provider):
    assert teacher.put(f"/settings/llm/keys/{provider}", json={"key": "sk-direct-secret"}).status_code == 204
    assert teacher.get("/settings/llm").json()["keys"][provider] is True


def test_anthropic_offers_use_its_own_auth_header_and_known_prices(teacher, monkeypatch):
    import io
    import json
    import urllib.request
    seen = {}

    def fake_urlopen(req, timeout):
        seen["url"], seen["headers"] = req.full_url, {k.lower(): v for k, v in req.header_items()}
        return io.BytesIO(json.dumps({"data": [{"id": "claude-haiku-5-5", "display_name": "Claude Haiku 5.5",
                                                "max_input_tokens": 1000000}]}).encode())
    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    teacher.put("/settings/llm/keys/anthropic", json={"key": "sk-ant-secret-1"})
    [offer] = teacher.get("/settings/llm/offers/anthropic").json()
    assert seen["url"].startswith("https://api.anthropic.com/v1/models")
    assert seen["headers"]["x-api-key"] == "sk-ant-secret-1" and "authorization" not in seen["headers"]
    assert seen["headers"]["anthropic-version"]
    assert offer["context_window"] == 1000000 and offer["pricing"] == {"input": 0.1, "output": 0.5}


def test_teacher_adds_direct_model_with_effort(teacher):
    body = {"provider": "anthropic", "model": "claude-haiku-5-5", "capabilities": ["reasoning"],
            "context_window": 1000000, "pricing": {"input": 0.1, "output": 0.5}, "effort": "low"}
    r = teacher.put("/settings/llm/models/anthropic/claude-haiku-5-5", json=body)
    assert r.status_code == 200 and r.json()["effort"] == "low"
