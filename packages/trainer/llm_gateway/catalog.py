"""Каталог моделей в БД поверх registry.yaml (решение пользователя 2026-10-08): модели добавляет администратор в
панели — из настоящего списка провайдера; запись в БД с тем же ключом, что в yaml, заменяет yaml-запись.
"""
import json
import logging
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import Engine, text
from sqlalchemy.exc import OperationalError


from .registry import ModelRegistry, ModelSpec

_log = logging.getLogger(__name__)

DEFAULT_LLM_ENDPOINTS = {
    "anthropic": "https://api.anthropic.com/v1",
    "openai": "https://api.openai.com/v1",
    "kimi": "https://api.moonshot.ai/v1",
    "zai": "https://api.z.ai/api/coding/paas/v4",
    "hf": "https://router.huggingface.co/v1",
    "openrouter": "https://openrouter.ai/api/v1",
}


@dataclass(frozen=True)
class Offer:
    """Модель из списка провайдера: id, название, окно контекста и цена за 1M токенов — если провайдер их отдаёт."""
    model: str
    name: str
    context_window: int | None = None
    pricing: dict | None = None


def _hf(item: dict) -> Offer:
    live = [p for p in item.get("providers") or [] if p.get("status") == "live"]
    priced = [p["pricing"] for p in live if p.get("pricing")]
    windows = [p["context_length"] for p in live if p.get("context_length")]
    # верхняя цена из провайдеров роутера — как в registry.yaml: лимиты не занижаем
    pricing = {"input": max(p["input"] for p in priced), "output": max(p["output"] for p in priced)} if priced else None
    return Offer(item["id"], item["id"], max(windows) if windows else None, pricing)


def _openrouter(item: dict) -> Offer:
    price = item.get("pricing") or {}
    pricing = None
    if price.get("prompt") is not None and price.get("completion") is not None:
        pricing = {"input": round(float(price["prompt"]) * 1_000_000, 6),
                   "output": round(float(price["completion"]) * 1_000_000, 6)}
    return Offer(item["id"], item.get("name") or item["id"], item.get("context_length"), pricing)


def parse_offers(provider: str, payload: dict) -> list[Offer]:
    items = payload.get("data") or []
    if provider == "hf":
        return [_hf(i) for i in items if i.get("id")]
    if provider == "openrouter":
        return [_openrouter(i) for i in items if i.get("id")]
    return [Offer(i["id"], i.get("display_name") or i["id"]) for i in items if i.get("id")]


KEY_ENV = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY", "kimi": "MOONSHOT_API_KEY",
           "zai": "ZAI_API_KEY", "hf": "HF_API_KEY", "openrouter": "OPENROUTER_API_KEY"}


def _with_endpoint(spec: ModelSpec) -> ModelSpec:
    """Адрес и имя ключа — всегда от провайдера, а не из записи каталога: каталог общий, и чужой адрес у модели
    увёл бы ключи всех пользователей на сервер автора записи. Свой адрес провайдера — только в коннекторе."""
    update: dict = {"api_key_env": KEY_ENV.get(spec.provider),
                    "base_url": None if spec.provider == "anthropic" else DEFAULT_LLM_ENDPOINTS.get(spec.provider)}
    if spec.provider == "zai" and spec.thinking is None:
        update["thinking"] = False  # glm на coding-плане тратит весь лимит вывода на рассуждение (2026-10-06)
    return spec.model_copy(update=update)


class ModelCatalog:
    def __init__(self, engine: Engine):
        self._engine = engine

    def specs(self) -> list[ModelSpec]:
        with self._engine.connect() as c:
            return [_with_endpoint(ModelSpec(key=r.key, **r.spec))
                    for r in c.execute(text("SELECT key, spec FROM llm_models ORDER BY key"))]

    def save(self, spec: ModelSpec, author: str) -> ModelSpec:
        body = spec.model_dump(exclude={"key", "base_url", "api_key_env"}, exclude_none=True)  # адрес — от провайдера
        with self._engine.begin() as c:
            c.execute(text("""
                INSERT INTO llm_models (key, spec, updated_by) VALUES (:k, CAST(:s AS jsonb), :a)
                ON CONFLICT (key) DO UPDATE SET spec = EXCLUDED.spec, updated_by = EXCLUDED.updated_by,
                    updated_at = now()"""), {"k": spec.key, "s": json.dumps(body, ensure_ascii=False), "a": author})
        return _with_endpoint(spec)

    def delete(self, key: str) -> bool:
        with self._engine.begin() as c:
            return c.execute(text("DELETE FROM llm_models WHERE key = :k"), {"k": key}).rowcount > 0

    def listing(self, yaml_path: Path | str) -> list[tuple[ModelSpec, str]]:
        """Итоговый каталог с источником записи: yaml, db или yaml+db (БД заменила yaml-запись)."""
        base = {m.key: m for m in ModelRegistry.load(yaml_path).all}
        db = {m.key: m for m in self.specs()}
        out = [(db.get(k, m), "yaml+db" if k in db else "yaml") for k, m in base.items()]
        out += [(m, "db") for k, m in db.items() if k not in base]
        return sorted(out, key=lambda x: x[0].key)


def load_registry(yaml_path: Path | str, engine: Engine | None) -> ModelRegistry:
    """Реестр для шлюза и API: registry.yaml + каталог БД (БД важнее)."""
    if engine is None:
        return ModelRegistry.load(yaml_path)
    try:
        return ModelRegistry([m for m, _src in ModelCatalog(engine).listing(yaml_path)],
                             ModelRegistry.load(yaml_path).provider_limits)
    except OperationalError as e:  # БД недоступна при сборке шлюза — модели из yaml; запуск сам упадёт на БД позже
        _log.warning("каталог моделей не прочитан (%s) — только registry.yaml", type(e).__name__)
        return ModelRegistry.load(yaml_path)
