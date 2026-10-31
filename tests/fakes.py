"""Подмены для API-тестов: модель в каталоге, поддельный провайдер LLM, синхронный запуск фоновых задач."""
import json

from trainer.llm_gateway.catalog import ModelCatalog
from trainer.llm_gateway.providers.base import ProviderResponse
from trainer.llm_gateway.providers.fake import FakeProvider
from trainer.llm_gateway.registry import ModelSpec, Pricing


def add_model(engine) -> None:
    ModelCatalog(engine).save(ModelSpec(key="openrouter/m", provider="openrouter", model="x/m",
                                        capabilities=["reasoning"], context_window=100000,
                                        pricing=Pricing(input=1.0, output=2.0)), author="test")


def reply(obj) -> ProviderResponse:
    body = obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False)
    return ProviderResponse(text=body, input_tokens=100, output_tokens=50, model="x/m")


def install_fake_llm(app, script: list) -> FakeProvider:
    """Все вызовы LLM в API идут в один сценарный провайдер; фоновые задачи выполняются сразу."""
    from apps.api.deps import providers_dep, runner_dep
    fake = FakeProvider("openrouter", script)
    app.dependency_overrides[providers_dep] = lambda: {"openrouter": fake}
    app.dependency_overrides[runner_dep] = lambda: (lambda fn, *a: fn(*a))
    return fake
