"""Модели и ключи LLM (только преподаватель). Ключ наружу не отдаётся никогда — только «задан/не задан»."""
import json
import re
import urllib.error
import urllib.request

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import Engine

from apps.api.auth import teacher_dep
from apps.api.deps import engine_dep, settings_dep
from trainer.llm.keys import PROVIDERS, LlmKeyStore
from trainer.llm.wiring import secret_box
from trainer.llm_gateway.catalog import ModelCatalog, parse_offers
from trainer.llm_gateway.registry import ModelSpec, model_source
from trainer.security.secrets import VaultNotConfigured
from trainer.settings import Settings

router = APIRouter(prefix="/settings/llm", dependencies=[Depends(teacher_dep)])
_KEY = re.compile(r"^[a-z]+/[A-Za-z0-9._:-]+$")
EDITABLE = {"provider", "model", "capabilities", "context_window", "pricing", "enabled", "thinking", "limits",
            "max_tokens_param"}
OFFERS_URL = {"openrouter": "https://openrouter.ai/api/v1/models", "hf": "https://router.huggingface.co/v1/models"}


def _keys(engine: Engine, settings: Settings) -> LlmKeyStore:
    return LlmKeyStore(engine, secret_box(settings))


def _provider_or_404(provider: str) -> None:
    if provider not in PROVIDERS:
        raise HTTPException(status_code=404, detail=f"провайдер {provider} не поддерживается")


@router.get("")
def overview(engine: Engine = Depends(engine_dep), settings: Settings = Depends(settings_dep)) -> dict:
    models = [{**m.model_dump(exclude={"api_key_env", "base_url"}), "source": src, "maker": model_source(m)}
              for m, src in ModelCatalog(engine).listing(settings.llm_registry_path)]
    return {"keys": _keys(engine, settings).status(), "models": models}


class KeyBody(BaseModel):
    key: str = Field(min_length=8, max_length=512)


@router.put("/keys/{provider}", status_code=204)
def set_key(provider: str, body: KeyBody, engine: Engine = Depends(engine_dep),
            settings: Settings = Depends(settings_dep)) -> None:
    _provider_or_404(provider)
    try:
        _keys(engine, settings).set(provider, body.key)
    except VaultNotConfigured as e:
        raise HTTPException(status_code=503, detail=str(e)) from e


@router.delete("/keys/{provider}", status_code=204)
def delete_key(provider: str, engine: Engine = Depends(engine_dep), settings: Settings = Depends(settings_dep)) -> None:
    _provider_or_404(provider)
    _keys(engine, settings).delete(provider)


@router.get("/offers/{provider}")
def offers(provider: str, engine: Engine = Depends(engine_dep), settings: Settings = Depends(settings_dep)) -> list[dict]:
    """Список моделей провайдера (для выбора в панели)."""
    _provider_or_404(provider)
    try:
        secret = _keys(engine, settings).get(provider)
    except VaultNotConfigured as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    if not secret:
        raise HTTPException(status_code=428, detail=f"сначала задайте ключ {provider}")
    req = urllib.request.Request(OFFERS_URL[provider], headers={"Authorization": f"Bearer {secret}"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:  # noqa: S310 — адрес фиксирован выше
            payload = json.loads(resp.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:  # тело не возвращаем — сервис может процитировать ключ
        raise HTTPException(status_code=502, detail=f"{provider}: список моделей не получен ({e.code})") from e
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
        raise HTTPException(status_code=502, detail=f"{provider}: список моделей не получен (сеть)") from e
    return [o.__dict__ for o in parse_offers(provider, payload)]


@router.put("/models/{key:path}")
def save_model(key: str, body: dict = Body(...), engine: Engine = Depends(engine_dep),
               who=Depends(teacher_dep)) -> dict:
    if not _KEY.match(key):
        raise HTTPException(status_code=422, detail="ключ модели — «провайдер/имя», латиница, цифры, . _ : -")
    fields = {k: v for k, v in body.items() if k in EDITABLE}
    try:
        spec = ModelSpec.model_validate({**fields, "key": key})
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=[err["msg"] for err in e.errors()]) from e
    if key.split("/", 1)[0] != spec.provider or spec.provider not in PROVIDERS:
        raise HTTPException(status_code=422, detail=f"ключ начинается с провайдера ({', '.join(PROVIDERS)})")
    return ModelCatalog(engine).save(spec, author=who.login).model_dump(exclude={"api_key_env", "base_url"})


@router.delete("/models/{key:path}", status_code=204)
def delete_model(key: str, engine: Engine = Depends(engine_dep)) -> None:
    if not ModelCatalog(engine).delete(key):
        raise HTTPException(status_code=404, detail=f"модели {key} нет")
