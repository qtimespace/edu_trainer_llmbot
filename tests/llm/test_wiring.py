import pytest
from sqlalchemy import text

from tests.helpers import PASS
from trainer.accounts.store import AccountStore
from trainer.domain import Budget
from trainer.llm.wiring import build_gateway, remaining_usd, spent_usd
from trainer.llm_gateway.catalog import ModelCatalog
from trainer.llm_gateway.gateway import GatewayRequest
from trainer.llm_gateway.providers.base import ProviderResponse
from trainer.llm_gateway.providers.fake import FakeProvider
from trainer.llm_gateway.registry import ModelSpec, Pricing
from trainer.settings import Settings


def _setup(engine):
    ModelCatalog(engine).save(ModelSpec(key="openrouter/m", provider="openrouter", model="x/m",
                                        capabilities=["reasoning"], context_window=100000,
                                        pricing=Pricing(input=1.0, output=2.0)), author="test")
    return AccountStore(engine).create_account("kid", PASS, role="student")


def test_gateway_records_spend_on_student(engine, database_url):
    kid = _setup(engine)
    fake = FakeProvider("openrouter", [ProviderResponse(text="{}", input_tokens=1000, output_tokens=500, model="x/m")])
    gw = build_gateway(engine, Settings(_env_file=None, database_url=database_url), student_id=kid.id,
                       providers={"openrouter": fake})
    gw.execute(GatewayRequest(task_id="t1", agent="devops", policy="tutor-v1", capabilities=[], system="s", user="u",
                              budget=Budget(max_input_tokens=10000, max_output_tokens=1000)))
    with engine.connect() as c:
        row = c.execute(text("SELECT user_id, agent, cost_usd FROM ledger")).one()
    assert row.user_id == kid.id and row.agent == "devops"
    assert spent_usd(engine, kid.id) == pytest.approx(0.002)


def test_remaining_budget(engine):
    kid = _setup(engine)
    with engine.begin() as c:
        c.execute(text("""INSERT INTO ledger (request_id, provider, model, input_tokens, output_tokens, cost_usd, agent,
                          task_id, user_id) VALUES ('r', 'openrouter', 'x/m', 1, 1, 0.75, 'devops', 't', :u)"""),
                  {"u": kid.id})
    assert remaining_usd(engine, kid.id, 1.0) == pytest.approx(0.25)
    assert remaining_usd(engine, kid.id, 0.5) == 0.0
