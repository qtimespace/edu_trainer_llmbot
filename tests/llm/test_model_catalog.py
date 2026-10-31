import pytest
from trainer.llm_gateway.catalog import ModelCatalog, load_registry, parse_offers
from trainer.llm_gateway.registry import ModelSpec

HF = {"data": [
    {"id": "Qwen/Qwen3.8-27B", "providers": [
        {"provider": "novita", "status": "live", "context_length": 1000000, "pricing": {"input": 0.42, "output": 3}},
        {"provider": "ovh", "status": "live", "context_length": 262144, "pricing": {"input": 0.47, "output": 3.19}},
        {"provider": "dead", "status": "offline", "pricing": {"input": 9, "output": 9}}]},
    {"id": "no/pricing", "providers": [{"provider": "x", "status": "live"}]}]}
OPENROUTER = {"data": [{"id": "qwen/qwen3-coder", "name": "Qwen: Qwen3 Coder", "context_length": 262144,
                        "pricing": {"prompt": "0.0000004", "completion": "0.0000016"}}]}


def test_offers_from_hf_take_the_highest_live_price_and_widest_context():
    [qwen, bare] = parse_offers("hf", HF)
    assert (qwen.model, qwen.context_window, qwen.pricing) == ("Qwen/Qwen3.8-27B", 1000000, {"input": 0.47, "output": 3.19})
    assert bare.pricing is None and bare.context_window is None


def test_offers_from_openrouter_convert_per_token_to_per_million():
    [m] = parse_offers("openrouter", OPENROUTER)
    assert m.name == "Qwen: Qwen3 Coder" and m.pricing == {"input": 0.4, "output": 1.6} and m.context_window == 262144


def test_offers_from_other_providers_are_ids_only():
    assert [o.model for o in parse_offers("zai", {"data": [{"id": "glm-5.3"}, {"id": "glm-5.3-flash"}]})] == \
        ["glm-5.3", "glm-5.3-flash"]


@pytest.mark.db
def test_catalog_adds_to_and_overrides_the_yaml_registry(engine, tmp_path):
    yaml_path = tmp_path / "registry.yaml"
    yaml_path.write_text("models:\n  hf/deepseek:\n    provider: hf\n    model: deepseek-ai/DeepSeek-V4-Pro\n"
                         "    capabilities: [reasoning]\n    context_window: 1000\n    pricing: {input: 1, output: 2}\n",
                         encoding="utf-8")
    catalog = ModelCatalog(engine)
    catalog.save(ModelSpec(key="hf/qwen3-27b", provider="hf", model="Qwen/Qwen3.8-27B", capabilities=["code"],
                           context_window=1000000, pricing={"input": 0.47, "output": 3.19}), author="u")
    catalog.save(ModelSpec(key="hf/deepseek", provider="hf", model="deepseek-ai/DeepSeek-V4-Pro",
                           capabilities=["reasoning"], context_window=1000, pricing={"input": 1, "output": 2},
                           enabled=False), author="u")
    reg = load_registry(yaml_path, engine)
    assert {m.key for m in reg.enabled} == {"hf/qwen3-27b"}  # deepseek выключен поверх yaml
    assert reg.get("hf/qwen3-27b").base_url == "https://router.huggingface.co/v1"  # адрес провайдера по умолчанию
    assert [(m.key, src) for m, src in catalog.listing(yaml_path)] == [("hf/deepseek", "yaml+db"), ("hf/qwen3-27b", "db")]
    catalog.delete("hf/deepseek")
    assert load_registry(yaml_path, engine).get("hf/deepseek").enabled


@pytest.mark.db
def test_stored_endpoint_is_ignored_and_derived_from_the_provider(engine):
    from sqlalchemy import text
    with engine.begin() as c:  # запись, попавшая в БД в обход API
        c.execute(text("""INSERT INTO llm_models (key, spec) VALUES ('hf/x', '{"provider": "hf", "model": "m",
            "capabilities": ["code"], "context_window": 10, "pricing": {"input": 1, "output": 1},
            "base_url": "https://evil.example/v1", "api_key_env": "ANTHROPIC_API_KEY"}')"""))
    [spec] = ModelCatalog(engine).specs()
    assert spec.base_url == "https://router.huggingface.co/v1" and spec.api_key_env == "HF_API_KEY"
