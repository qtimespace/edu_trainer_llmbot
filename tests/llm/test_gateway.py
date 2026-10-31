import pytest
from trainer.domain import Budget
from trainer.llm_gateway.errors import ProviderError
from trainer.llm_gateway.gateway import GatewayError, GatewayRequest, LLMGateway
from trainer.llm_gateway.health import CircuitBreaker
from trainer.llm_gateway.ledger import InMemoryLedger
from trainer.llm_gateway.policy import Constraints, FallbackRules, Policy, Quality
from trainer.llm_gateway.providers import FakeProvider, ProviderResponse
from trainer.llm_gateway.registry import ModelRegistry, ModelSpec, Pricing


def spec(key, provider, price_in=2.0, price_out=10.0, caps=("reasoning", "code"), window=200_000):
    return ModelSpec(key=key, provider=provider, model=key.split("/")[1], capabilities=list(caps),
                     context_window=window, pricing=Pricing(input=price_in, output=price_out))


REGISTRY = ModelRegistry([
    spec("anthropic/big", "anthropic", 5.0, 25.0),
    spec("anthropic/small", "anthropic", 2.0, 10.0),
    spec("openai/mid", "openai", 1.0, 4.0),
])


def policy(execution="fallback", max_attempts=3, max_cost=0.20, strategy=("next_model", "cheaper_model")):
    return Policy(name="p", execution=execution,
                  constraints=Constraints(max_cost_usd=max_cost, max_input_tokens=12000,
                                          max_output_tokens=3000, max_attempts=max_attempts),
                  preferred=["reasoning", "code"],
                  fallback=FallbackRules(on=["timeout", "provider_error", "rate_limit", "quota_exceeded"],
                                         strategy=list(strategy)),
                  quality=Quality(min_confidence=0.85))


def ok(model="m", text='{"status":"pass"}'):
    return ProviderResponse(text=text, input_tokens=1000, output_tokens=200, model=model)


def req(user="Проверь", budget=None):
    return GatewayRequest(task_id="t1", agent="documentation_auditor", policy="p",
                          capabilities=["reasoning", "code"], system="sys", user=user,
                          budget=budget or Budget(max_input_tokens=12000, max_output_tokens=3000, max_usd=0.2))


def gateway(anthropic_script, openai_script=(), pol=None, breaker=None, ledger=None):
    providers = {"anthropic": FakeProvider("anthropic", list(anthropic_script)),
                 "openai": FakeProvider("openai", list(openai_script))}
    gw = LLMGateway(REGISTRY, {"p": pol or policy()}, providers, breaker=breaker, ledger=ledger)
    return gw, providers


def test_first_model_success_is_recorded_in_ledger():
    ledger = InMemoryLedger()
    gw, prov = gateway([ok("big")], ledger=ledger)
    resp = gw.execute(req())
    assert resp.model_key == "anthropic/big" and resp.text == '{"status":"pass"}'
    assert resp.cost_usd == pytest.approx((1000 * 5 + 200 * 25) / 1e6)
    assert ledger.entries[0].task_id == "t1" and ledger.entries[0].agent == "documentation_auditor"
    assert prov["anthropic"].calls[0].model == "big"


def test_timeout_is_retried_on_same_model():
    gw, prov = gateway([ProviderError("timeout"), ok("big")])
    assert gw.execute(req()).model_key == "anthropic/big"
    assert [c.model for c in prov["anthropic"].calls] == ["big", "big"]


def test_rate_limit_switches_provider():
    gw, prov = gateway([ProviderError("rate_limit")], [ok("mid")])
    assert gw.execute(req()).model_key == "openai/mid"
    assert [c.model for c in prov["anthropic"].calls] == ["big"]


def test_provider_error_moves_to_next_model():
    gw, _ = gateway([ProviderError("provider_error"), ok("small")])
    assert gw.execute(req()).model_key == "anthropic/small"


def test_kind_outside_policy_stops_immediately():
    gw, prov = gateway([ProviderError("auth")], [ok("mid")])
    with pytest.raises(GatewayError) as e:
        gw.execute(req())
    assert e.value.reason == "auth"
    assert prov["openai"].calls == []


def test_refusal_is_not_retried_elsewhere():
    gw, _ = gateway([ProviderError("refusal")], [ok("mid")])
    with pytest.raises(GatewayError) as e:
        gw.execute(req())
    assert e.value.reason == "refusal"


def test_all_fail_is_exhausted_with_attempts():
    gw, _ = gateway([ProviderError("provider_error"), ProviderError("provider_error")],
                    [ProviderError("provider_error")])
    with pytest.raises(GatewayError) as e:
        gw.execute(req())
    assert e.value.reason == "exhausted"
    assert [a.model_key for a in e.value.attempts] == ["anthropic/big", "anthropic/small", "openai/mid"]


def test_max_attempts_caps_calls():
    gw, prov = gateway([ProviderError("provider_error"), ProviderError("provider_error")],
                       [ok("mid")], pol=policy(max_attempts=2))
    with pytest.raises(GatewayError) as e:
        gw.execute(req())
    assert e.value.reason == "max_attempts"
    assert prov["openai"].calls == []


def test_budget_skips_expensive_model_for_cheaper():
    # резерв big = 3000 * 25 / 1e6 ≈ 0.075 > 0.05; small = 3000 * 10 / 1e6 ≈ 0.03
    gw, prov = gateway([ok("small")], pol=policy(max_cost=0.05))
    resp = gw.execute(req())
    assert resp.model_key == "anthropic/small"
    assert resp.attempts[0].outcome == "skipped_budget"
    assert [c.model for c in prov["anthropic"].calls] == ["small"]


def test_budget_without_cheaper_strategy_fails():
    gw, _ = gateway([ok("small")], pol=policy(max_cost=0.05, strategy=("next_model",)))
    with pytest.raises(GatewayError) as e:
        gw.execute(req())
    assert e.value.reason == "budget_exceeded"


def test_open_breaker_skips_provider():
    breaker = CircuitBreaker(failure_threshold=1)
    breaker.record_failure("anthropic")
    gw, prov = gateway([], [ok("mid")], breaker=breaker)
    assert gw.execute(req()).model_key == "openai/mid"
    assert prov["anthropic"].calls == []


def test_context_overflow_rejected_before_any_call():
    gw, prov = gateway([ok("big")])
    with pytest.raises(GatewayError) as e:
        gw.execute(req(user="ы" * 40_000))
    assert e.value.reason == "context_overflow"
    assert prov["anthropic"].calls == []


def test_single_execution_does_not_fall_back():
    gw, _ = gateway([ProviderError("provider_error"), ok("small")], pol=policy(execution="single"))
    with pytest.raises(GatewayError) as e:
        gw.execute(req())
    assert e.value.reason == "exhausted"


def test_request_budget_tightens_policy():
    gw, prov = gateway([ok("big")])
    gw.execute(req(budget=Budget(max_input_tokens=12000, max_output_tokens=500, max_usd=0.2)))
    assert prov["anthropic"].calls[0].max_output_tokens == 500


def test_auth_and_quota_errors_do_not_open_the_shared_breaker():
    breaker = CircuitBreaker(failure_threshold=1)
    for kind in ("auth", "quota_exceeded"):
        gw, _ = gateway([ProviderError(kind), ProviderError(kind)], [ok("mid")], breaker=breaker)
        try:
            gw.execute(req())
        except GatewayError:
            pass
    assert breaker.state("anthropic") == "healthy"


def routed(route=None, exclude=()):
    r = req()
    return r.model_copy(update={"route": route, "exclude_providers": list(exclude)})


def test_route_sets_exact_candidates_and_order():
    gw, prov = gateway([ok("small")], [ProviderError("provider_error")])
    resp = gw.execute(routed(["openai/mid", "anthropic/small"]))
    assert resp.model_key == "anthropic/small"
    assert [c.model for c in prov["openai"].calls] == ["mid"]
    assert [c.model for c in prov["anthropic"].calls] == ["small"]


def test_exclude_providers_applies_to_fallback_too():
    gw, prov = gateway([ok("big")], [ProviderError("provider_error")])
    with pytest.raises(GatewayError) as e:
        gw.execute(routed(["openai/mid", "anthropic/big"], exclude=["anthropic"]))
    assert e.value.reason == "exhausted" and prov["anthropic"].calls == []


def test_everything_excluded_is_no_candidates():
    gw, _ = gateway([ok("big")])
    with pytest.raises(GatewayError) as e:
        gw.execute(routed(None, exclude=["anthropic", "openai"]))
    assert e.value.reason == "no_candidates"


def test_unknown_route_key_is_ignored():
    gw, _ = gateway([ok("big")])
    assert gw.execute(routed(["nope/x", "anthropic/big"])).model_key == "anthropic/big"


def test_model_thinking_flag_reaches_the_provider_and_failed_attempt_cost_is_reported():
    registry = ModelRegistry([spec("anthropic/big", "anthropic").model_copy(update={"thinking": False}),
                              spec("openai/mid", "openai", 1.0, 4.0)])
    truncated = ProviderError("provider_error", "output truncated at max tokens", (1000, 3000))
    providers = {"anthropic": FakeProvider("anthropic", [truncated]), "openai": FakeProvider("openai", [ok("mid")])}
    gw = LLMGateway(registry, {"p": policy()}, providers)
    resp = gw.execute(req())
    assert providers["anthropic"].calls[0].thinking is False and providers["openai"].calls[0].thinking is None
    # неудачная попытка стоила денег — она видна в ответе, а не только в журнале шлюза
    assert resp.failed_cost_usd == pytest.approx((1000 * 2 + 3000 * 10) / 1e6)
    broken = LLMGateway(registry, {"p": policy()}, {"anthropic": FakeProvider("anthropic", [truncated]),
                                                    "openai": FakeProvider("openai", [truncated])})
    with pytest.raises(GatewayError) as e:
        broken.execute(req())
    assert e.value.cost_usd == pytest.approx((1000 * 2 + 3000 * 10 + 1000 * 1 + 3000 * 4) / 1e6)


def test_registry_switches_off_reasoning_for_zai_models():
    from trainer.settings import Settings
    registry = ModelRegistry.load(Settings(_env_file=None).llm_registry_path)
    assert all(m.thinking is False for m in registry.all if m.provider == "zai")


def test_model_source_is_the_maker_behind_a_router():
    from trainer.llm_gateway.registry import model_source

    def m(key, provider, model):
        return ModelSpec(key=key, provider=provider, model=model, capabilities=["reasoning"], context_window=1000,
                         pricing=Pricing(input=1, output=1))
    assert model_source(m("hf/ds", "hf", "deepseek-ai/DeepSeek-V4-Pro")) == "deepseek"
    assert model_source(m("hf/qw", "hf", "Qwen/Qwen3.8-27B")) == "qwen"
    assert model_source(m("hf/g", "hf", "google/gemma-4-31B-it")) == "google"
    assert model_source(m("openrouter/s", "openrouter", "anthropic/claude-sonnet-5.5")) == "anthropic"
    assert model_source(m("openrouter/o", "openrouter", "openai/gpt-6")) == "openai"
    assert model_source(m("anthropic/s", "anthropic", "claude-sonnet-5")) == "anthropic"  # прямой — сам себе источник
    assert model_source(m("zai/glm", "zai", "glm-5.3")) == "zai"
    assert model_source(m("hf/x", "hf", "deepseek-ai/x").model_copy(update={"maker": "custom"})) == "custom"


def test_exclusion_is_by_source_so_two_makers_on_one_router_stay_independent():
    registry = ModelRegistry([
        ModelSpec(key="hf/ds", provider="hf", model="deepseek-ai/DeepSeek-V4-Pro", capabilities=["reasoning"],
                  context_window=200_000, pricing=Pricing(input=1, output=1)),
        ModelSpec(key="hf/qw", provider="hf", model="Qwen/Qwen3.8-27B", capabilities=["reasoning"],
                  context_window=200_000, pricing=Pricing(input=1, output=1))])
    prov = {"hf": FakeProvider("hf", [ok("Qwen/Qwen3.8-27B")])}
    gw = LLMGateway(registry, {"p": policy()}, prov, ledger=InMemoryLedger())
    resp = gw.execute(req().model_copy(update={"route": ["hf/ds", "hf/qw"], "exclude_providers": ["deepseek"]}))
    assert resp.model_key == "hf/qw" and resp.source == "qwen"  # автор на deepseek — проверяет qwen на том же hf
