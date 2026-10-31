import pytest
from sqlalchemy import text

from trainer.llm_gateway.budget import BudgetTracker, estimate_tokens
from trainer.llm_gateway.health import CircuitBreaker
from trainer.llm_gateway.ledger import InMemoryLedger, LedgerEntry, PostgresLedger


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def test_breaker_lifecycle():
    clock = Clock()
    b = CircuitBreaker(failure_threshold=3, cooldown_seconds=60, clock=clock)
    assert b.state("anthropic") == "healthy"
    b.record_failure("anthropic")
    assert b.state("anthropic") == "degraded" and b.allow("anthropic")
    b.record_failure("anthropic")
    b.record_failure("anthropic")
    assert b.state("anthropic") == "open" and not b.allow("anthropic")
    clock.now = 61
    assert b.state("anthropic") == "half_open" and b.allow("anthropic")
    b.record_failure("anthropic")
    assert b.state("anthropic") == "open"
    clock.now = 130
    b.record_success("anthropic")
    assert b.state("anthropic") == "healthy"
    assert b.state("openai") == "healthy"


def test_budget_reserve_and_settle():
    t = BudgetTracker(max_usd=0.20)
    assert t.reserve(0.15)
    assert not t.reserve(0.10)
    t.settle(0.15, 0.04)
    assert t.spent == pytest.approx(0.04)
    assert t.remaining == pytest.approx(0.16)
    assert t.reserve(0.10)


def test_estimate_tokens_is_conservative():
    assert estimate_tokens("") == 0
    assert estimate_tokens("абв") == 1
    assert estimate_tokens("x" * 3001) == 1001


def entry(cost=0.0315):
    return LedgerEntry(request_id="r1", provider="anthropic", model="claude-opus-5", input_tokens=4312,
                       output_tokens=1120, cost_usd=cost, agent="documentation_auditor", task_id="t1")


def test_in_memory_ledger():
    led = InMemoryLedger()
    led.record(entry())
    assert led.entries[0].model == "claude-opus-5"


@pytest.mark.db
def test_postgres_ledger_records_numeric_cost(engine):
    PostgresLedger(engine).record(entry(0.03149))
    with engine.connect() as c:
        row = c.execute(text("select provider, cost_usd, agent from ledger")).one()
    assert row.provider == "anthropic" and float(row.cost_usd) == pytest.approx(0.0315)


@pytest.mark.db
def test_postgres_ledger_attributes_user_and_project(engine):
    from sqlalchemy import text

    from trainer.llm_gateway.ledger import LedgerEntry, PostgresLedger
    PostgresLedger(engine, user_id="u-a", project_id="p-1").record(LedgerEntry(
        request_id="r", provider="hf", model="m", input_tokens=1, output_tokens=1, cost_usd=0.001,
        agent="automation:reqcheck", task_id="t"))
    with engine.connect() as c:
        row = c.execute(text("SELECT user_id, project_id FROM ledger")).one()
    assert (row.user_id, row.project_id) == ("u-a", "p-1")
