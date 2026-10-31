from fastapi import Depends
from sqlalchemy import Engine

from trainer.db import get_engine
from trainer.settings import Settings, get_settings


def settings_dep() -> Settings:
    return get_settings()


def engine_dep(settings: Settings = Depends(settings_dep)) -> Engine:
    return get_engine(settings.database_url)


def providers_dep():
    """Провайдеры LLM: None — настоящие (по ключам преподавателя); тесты подменяют сценарным."""
    return None


def runner_dep():
    """Запуск фоновой работы (вызовы LLM): поток-демон; тесты подменяют синхронным вызовом."""
    from trainer.tutor.jobs import run_background
    return run_background
