import pytest
from trainer.llm_gateway.errors import ProviderError
from trainer.llm_gateway.gateway import GatewayError, LLMGateway
from trainer.llm_gateway.ledger import InMemoryLedger
from trainer.llm_gateway.limits import (
    InMemoryCooldowns,
    InMemoryUsage,
    LimitGuard,
    Limits,
    retry_after_seconds,
)
from trainer.llm_gateway.providers import FakeProvider
from trainer.llm_gateway.registry import ModelRegistry

from tests.llm.test_gateway import ok, policy, req, spec

NOW = 1_000_000.0


class Clock:
    def __init__(self):
        self.t, self.slept = NOW, []

    def __call__(self):
        return self.t

    def sleep(self, s):
        self.slept.append(s)
        self.t += s


def setup(big_limits=None, provider_limits=None, script_a=(), script_o=()):
    big = spec("anthropic/big", "anthropic", 5.0, 25.0).model_copy(update={"limits": big_limits})
    registry = ModelRegistry([big, spec("openai/mid", "openai", 1.0, 4.0)], provider_limits=provider_limits or {})
    clock = Clock()
    usage, cooldowns = InMemoryUsage(clock), InMemoryCooldowns(clock)
    guard = LimitGuard(usage, cooldowns, registry.provider_limits, clock=clock, sleep=clock.sleep)
    ledger = InMemoryLedger()
    providers = {"anthropic": FakeProvider("anthropic", list(script_a)), "openai": FakeProvider("openai", list(script_o))}
    gw = LLMGateway(registry, {"p": policy()}, providers, ledger=ledger, limits=guard)
    return gw, providers, usage, cooldowns, clock


def test_a_model_over_its_minute_limit_is_skipped_for_the_next_one():
    gw, prov, usage, _cd, _clock = setup(Limits(rpm=2), script_o=[ok("mid")])
    usage.add("model", "anthropic/big", 100, at=NOW - 10)
    usage.add("model", "anthropic/big", 100, at=NOW - 5)
    resp = gw.execute(req())
    assert resp.model_key == "openai/mid" and prov["anthropic"].calls == []
    assert resp.attempts[0].outcome == "skipped_limit" and "в минуту" in resp.attempts[0].error_kind


def test_a_request_that_would_not_fit_the_token_limit_is_not_sent():
    gw, prov, usage, _cd, _clock = setup(Limits(tpm=4000), script_o=[ok("mid")])
    usage.add("model", "anthropic/big", 2000, at=NOW - 1)  # + оценка запроса (вход + 3000 выхода) > 4000
    assert gw.execute(req()).model_key == "openai/mid" and prov["anthropic"].calls == []


def test_429_pauses_the_model_for_retry_after_and_the_next_call_skips_it():
    err = ProviderError("rate_limit", "slow down", retry_after=120)
    gw, prov, _usage, cooldowns, _clock = setup(script_a=[err], script_o=[ok("mid"), ok("mid")])
    assert gw.execute(req()).model_key == "openai/mid"
    until, why = cooldowns.get("model", "anthropic/big")
    assert until == NOW + 120 and "429" in why
    assert gw.execute(req()).model_key == "openai/mid" and len(prov["anthropic"].calls) == 1


def test_a_quota_error_pauses_every_model_of_the_provider_for_an_hour():
    gw, _prov, _usage, cooldowns, _clock = setup(script_a=[ProviderError("quota_exceeded", "no credits")],
                                                 script_o=[ok("mid")])
    gw.execute(req())
    until, why = cooldowns.get("provider", "anthropic")
    assert until == NOW + 3600 and "квот" in why


def test_all_models_paused_briefly_waits_once_and_retries():
    gw, _prov, _usage, cooldowns, clock = setup(script_a=[ok("big")])
    cooldowns.set("model", "anthropic/big", NOW + 20, "429")
    cooldowns.set("provider", "openai", NOW + 3600, "квота")
    assert gw.execute(req()).model_key == "anthropic/big" and len(clock.slept) == 1 and 20 < clock.slept[0] < 23


def test_all_models_paused_for_long_is_an_error_with_the_time():
    gw, _prov, _usage, cooldowns, clock = setup()
    cooldowns.set("model", "anthropic/big", NOW + 600, "429")
    cooldowns.set("provider", "openai", NOW + 3600, "квота")
    with pytest.raises(GatewayError) as e:
        gw.execute(req())
    assert e.value.reason == "rate_limited" and e.value.retry_at == NOW + 600 and clock.slept == []


def test_a_provider_wide_daily_limit_counts_every_model_of_the_provider():
    gw, prov, usage, _cd, _clock = setup(provider_limits={"anthropic": Limits(rpd=1)}, script_o=[ok("mid")])
    usage.add("provider", "anthropic", 10, at=NOW - 3600)
    assert gw.execute(req()).model_key == "openai/mid" and prov["anthropic"].calls == []


def test_a_successful_call_counts_toward_both_the_model_and_its_provider():
    gw, _prov, usage, _cd, _clock = setup(script_a=[ok("big")])
    gw.execute(req())
    assert usage.window("model", "anthropic/big", 60).requests == 1
    assert usage.window("provider", "anthropic", 86400).tokens == 1200


def test_retry_after_accepts_seconds_and_http_dates():
    assert retry_after_seconds("30", now=NOW) == 30
    assert retry_after_seconds("Wed, 21 Oct 2015 07:28:00 GMT", now=1445412480.0) == 0
    assert retry_after_seconds("бред", now=NOW) is None and retry_after_seconds(None, now=NOW) is None


def test_without_limits_the_gateway_behaves_as_before():
    gw, _prov, _usage, _cd, _clock = setup(script_a=[ok("big")])
    assert gw.execute(req()).model_key == "anthropic/big"


def test_a_request_bigger_than_the_token_limit_is_never_sent_and_not_waited_for():
    # ревью 1: запрос больше tpm не пройдёт никогда — ждать 60 с и писать «на паузе до …» было неправдой
    gw, prov, _usage, _cd, clock = setup(Limits(tpm=3000))  # оценка запроса: вход + 3000 выхода > 3000
    gw2, *_ = setup(Limits(tpm=3000), script_o=[ok("mid")])
    assert gw2.execute(req()).model_key == "openai/mid"
    gw._providers.pop("openai")
    with pytest.raises(GatewayError) as e:
        gw.execute(req())
    assert e.value.reason == "rate_limited" and e.value.retry_at is None and clock.slept == []
    assert "больше лимита" in e.value.attempts[0].error_kind and prov["anthropic"].calls == []


def test_the_wait_is_until_the_latest_of_the_blocking_limits():
    # ревью 5: rpm освободится через 20 с, а tpd — через 5 ч: ждать 20 с бессмысленно
    gw, _prov, usage, _cd, clock = setup(Limits(rpm=1, tpd=5000))
    gw._providers.pop("openai")
    usage.add("model", "anthropic/big", 4000, at=NOW - 40)
    with pytest.raises(GatewayError) as e:
        gw.execute(req())
    assert clock.slept == [] and e.value.retry_at == NOW - 40 + 86400


def test_the_wait_leaves_a_little_slack_for_clock_skew():
    # ревью 4: окно считает Postgres, ожидание — часы воркера: ровно на границе второй круг снова упирался
    gw, _prov, _usage, cooldowns, clock = setup(script_a=[ok("big")])
    gw._providers.pop("openai")
    cooldowns.set("model", "anthropic/big", NOW + 20, "429")
    gw.execute(req())
    assert clock.slept and clock.slept[0] > 20
