import time

import pytest
from trainer.llm_gateway.ledger import LedgerEntry, PostgresLedger
from trainer.llm_gateway.limits import PgCooldowns, PgUsage

pytestmark = pytest.mark.db


def entry(model_key="or/free", provider="openrouter", tokens=(100, 50)):
    return LedgerEntry(request_id="r", provider=provider, model="x", model_key=model_key, input_tokens=tokens[0],
                       output_tokens=tokens[1], cost_usd=0.0, agent="a", task_id="t")


def test_usage_windows_come_from_the_ledger_per_user(engine):
    PostgresLedger(engine, user_id="u1", project_id="p").record(entry())
    PostgresLedger(engine, user_id="u1", project_id="p").record(entry(model_key="or/other"))
    PostgresLedger(engine, user_id="u2", project_id="p").record(entry())
    mine = PgUsage(engine, "u1")
    w = mine.window("model", "or/free", 60)
    assert (w.requests, w.tokens) == (1, 150) and w.oldest and abs(w.oldest - time.time()) < 120
    assert mine.window("provider", "openrouter", 86400).requests == 2
    assert PgUsage(engine, "u3").window("model", "or/free", 60).requests == 0  # чужой расход не считается


def test_cooldowns_are_per_user_expire_and_can_be_cleared(engine):
    a, b = PgCooldowns(engine, "u1"), PgCooldowns(engine, "u2")
    a.set("model", "or/free", time.time() + 120, "429")
    assert a.get("model", "or/free")[1] == "429" and b.get("model", "or/free") is None
    a.set("provider", "zai", time.time() - 1, "квота")
    assert a.get("provider", "zai") is None  # истекла
    assert [x["key"] for x in a.active()] == ["or/free"]
    assert a.clear("model", "or/free") is True and a.get("model", "or/free") is None


def test_the_registry_from_the_panel_catalog_keeps_provider_limits_and_model_limits(engine, tmp_path):
    from trainer.llm_gateway.catalog import ModelCatalog, load_registry
    from trainer.llm_gateway.limits import Limits
    from trainer.llm_gateway.registry import ModelSpec, Pricing
    yaml_path = tmp_path / "registry.yaml"
    yaml_path.write_text("provider_limits:\n  openrouter: {rpd: 50}\nmodels:\n  or/free:\n    provider: openrouter\n"
                         "    model: x/y:free\n    capabilities: [reasoning]\n    context_window: 1000\n"
                         "    pricing: {input: 0, output: 0}\n", encoding="utf-8")
    ModelCatalog(engine).save(ModelSpec(key="or/free", provider="openrouter", model="x/y:free",
                                        capabilities=["reasoning"], context_window=1000,
                                        pricing=Pricing(input=0, output=0), limits=Limits(rpm=20)), author="a")
    registry = load_registry(yaml_path, engine)
    assert registry.provider_limits["openrouter"].rpd == 50
    assert registry.get("or/free").limits.rpm == 20



def test_a_later_shorter_429_does_not_shorten_a_running_pause(engine):
    # ревью: последний писатель выигрывал — 429 с Retry-After 5 с укорачивал паузу в 120 с
    a = PgCooldowns(engine, "u9")
    a.set("model", "m", time.time() + 120, "429")
    a.set("model", "m", time.time() + 5, "429")
    assert a.get("model", "m")[0] > time.time() + 100


def test_usage_of_a_run_without_a_user_is_its_own_bucket(engine):
    PostgresLedger(engine, user_id=None, project_id="p").record(entry(model_key="dev/m"))
    assert PgUsage(engine, None).window("model", "dev/m", 60).requests == 1
    assert PgUsage(engine, "u1").window("model", "dev/m", 60).requests == 0
