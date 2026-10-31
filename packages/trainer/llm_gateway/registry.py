from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, model_validator

from .limits import Limits


class Pricing(BaseModel):
    input: float = Field(ge=0)
    output: float = Field(ge=0)


# Роутеры: за ними модели разных производителей — независимость проверяющего считается по производителю модели
AGGREGATORS = frozenset({"hf", "openrouter"})
# организация в id модели у роутера → источник (производитель); прочие — как есть, в нижнем регистре
_MAKERS = {"deepseek-ai": "deepseek", "qwen": "qwen", "google": "google", "meta-llama": "meta",
           "anthropic": "anthropic", "openai": "openai", "z-ai": "zai", "zai-org": "zai", "thudm": "zai",
           "mistralai": "mistral", "moonshotai": "kimi", "x-ai": "xai"}


class ModelSpec(BaseModel):
    key: str
    provider: Literal["anthropic", "openai", "kimi", "zai", "hf", "openrouter"]
    model: str = ""
    capabilities: list[str]
    context_window: int = Field(gt=0)
    pricing: Pricing
    enabled: bool = True
    base_url: str | None = None
    api_key_env: str | None = None
    server_side_fallback: bool = False
    effort: Literal["low", "medium", "high", "xhigh", "max"] | None = None
    max_tokens_param: str = "max_tokens"
    # рассуждение модели: False — выключить (Z.AI glm тратил на него весь лимит вывода), None — по умолчанию API
    thinking: bool | None = None
    # производитель модели — для правила «проверяющий независим от авторов»; пусто — вычисляется (model_source)
    maker: str | None = None
    # лимиты на ключ пользователя: запросы/токены в минуту и в сутки (None — без лимита)
    limits: Limits | None = None

    @model_validator(mode="after")
    def _enabled_needs_model(self) -> "ModelSpec":
        if self.enabled and not self.model:
            raise ValueError(f"model {self.key}: enabled but 'model' id is empty")
        return self

    def cost_usd(self, input_tokens: int, output_tokens: int) -> float:
        return (input_tokens * self.pricing.input + output_tokens * self.pricing.output) / 1_000_000


def load_provider_limits(raw: dict) -> dict[str, Limits]:
    return {k: Limits(**v) for k, v in (raw.get("provider_limits") or {}).items()}


def model_source(spec: ModelSpec) -> str:
    """Производитель модели: у прямого провайдера — он сам, у роутера (hf, openrouter) — организация из id модели."""
    if spec.maker:
        return spec.maker
    if spec.provider not in AGGREGATORS or "/" not in spec.model:
        return spec.provider
    org = spec.model.split("/", 1)[0].strip().lower()
    return _MAKERS.get(org, org) or spec.provider


class ModelRegistry:
    def __init__(self, models: list[ModelSpec], provider_limits: dict[str, Limits] | None = None):
        self._models = list(models)
        self.provider_limits = dict(provider_limits or {})  # общий лимит ключа у провайдера (OpenRouter :free)

    @classmethod
    def load(cls, path: Path | str) -> "ModelRegistry":
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        return cls([ModelSpec(key=k, **v) for k, v in raw["models"].items()], load_provider_limits(raw))

    @property
    def all(self) -> list[ModelSpec]:
        """Полный реестр, включая выключенные модели: выключенная — известная, но недоступная."""
        return list(self._models)

    @property
    def enabled(self) -> list[ModelSpec]:
        return [m for m in self._models if m.enabled]

    def candidates(self, capabilities: list[str]) -> list[ModelSpec]:
        need = set(capabilities)
        return [m for m in self.enabled if need <= set(m.capabilities)]

    def get(self, key: str) -> ModelSpec:
        return next(m for m in self._models if m.key == key)
