"""Сборка шлюза LLM: ключи преподавателя, расход — на ученика, лимиты и паузы — общие на ключ."""
import logging

from sqlalchemy import Engine, text

from trainer.llm.keys import LlmKeyStore
from trainer.llm_gateway.catalog import load_registry
from trainer.llm_gateway.gateway import LLMGateway
from trainer.llm_gateway.health import CircuitBreaker
from trainer.llm_gateway.ledger import PostgresLedger
from trainer.llm_gateway.limits import LimitGuard, PgCooldowns, PgUsage
from trainer.llm_gateway.policy import load_policies
from trainer.llm_gateway.providers.base import Provider
from trainer.llm_gateway.registry import ModelRegistry
from trainer.security.secrets import SecretBox
from trainer.settings import Settings, get_settings

log = logging.getLogger(__name__)
_BREAKER = CircuitBreaker()  # общий на процесс: упавший провайдер не дёргаем каждым учеником


def secret_box(settings: Settings | None = None) -> SecretBox | None:
    import os
    spec = (settings.secrets_keys if settings else "") or os.environ.get("TRAINER_SECRETS_KEYS", "")
    try:
        return SecretBox.from_spec(spec)
    except ValueError as e:
        log.error("TRAINER_SECRETS_KEYS не разобран: %s — хранилище ключей выключено", e)
        return None


def build_providers(registry: ModelRegistry, keys: LlmKeyStore) -> dict[str, Provider]:
    from trainer.llm_gateway.providers.openai_compat import OpenAICompatibleProvider
    providers: dict[str, Provider] = {}
    for spec in registry.enabled:
        if spec.provider in providers:
            continue
        key = keys.get(spec.provider)
        if key:  # без ключа провайдер не подключается: его модели просто не участвуют в маршруте
            providers[spec.provider] = OpenAICompatibleProvider(spec.provider, base_url=spec.base_url, api_key=key)
    return providers


def build_gateway(engine: Engine, settings: Settings | None = None, *, student_id: str | None,
                  providers: dict[str, Provider] | None = None) -> LLMGateway:
    settings = settings or get_settings()
    registry = load_registry(settings.llm_registry_path, engine)
    if providers is None:
        providers = build_providers(registry, LlmKeyStore(engine, secret_box(settings)))
    limits = LimitGuard(PgUsage(engine, "*"), PgCooldowns(engine, None), registry.provider_limits)
    return LLMGateway(registry, load_policies(settings.llm_policies_dir), providers, breaker=_BREAKER,
                      limits=limits, ledger=PostgresLedger(engine, user_id=student_id))


def spent_usd(engine: Engine, student_id: str) -> float:
    with engine.connect() as c:
        return float(c.execute(text("SELECT COALESCE(sum(cost_usd), 0) FROM ledger WHERE user_id = :u"),
                               {"u": student_id}).scalar_one())


def remaining_usd(engine: Engine, student_id: str, budget_usd: float) -> float:
    return max(0.0, budget_usd - spent_usd(engine, student_id))
