import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from trainer.db import make_engine

os.environ.setdefault("TRAINER_SECRETS_KEYS", "k1:" + "QUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUE=")

ROOT = Path(__file__).resolve().parents[1]
TABLES = ("task_messages", "agent_jobs", "tasks", "lessons", "agents", "llm_cooldowns", "ledger", "llm_models",
          "llm_keys", "presence", "group_students", "groups", "login_attempts", "sessions", "accounts")


def _to_sqlalchemy(uri: str) -> str:
    return uri.replace("postgresql://", "postgresql+psycopg://", 1)


@pytest.fixture(scope="session")
def database_url(tmp_path_factory):
    url = os.environ.get("TRAINER_TEST_DATABASE_URL")
    server = None
    if not url:
        import pgserver

        server = pgserver.get_server(str(tmp_path_factory.mktemp("pg")), cleanup_mode="stop")
        url = _to_sqlalchemy(server.get_uri())
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "infra" / "migrations"))
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")
    yield url
    if server is not None:
        server.cleanup()


@pytest.fixture
def engine(database_url):
    eng = make_engine(database_url)
    yield eng
    with eng.begin() as conn:
        conn.execute(text("TRUNCATE " + ", ".join(TABLES) + " CASCADE"))
    eng.dispose()


@pytest.fixture
def api(engine, database_url):
    """Приложение API на тестовой БД: подменяются настройки и движок; возвращает движок."""
    from apps.api.deps import engine_dep, settings_dep
    from apps.api.main import app
    from trainer.settings import Settings

    settings = Settings(_env_file=None, database_url=database_url, session_cookie_secure=False,
                        secrets_keys=os.environ["TRAINER_SECRETS_KEYS"], sandbox_backend="fake")
    app.dependency_overrides[settings_dep] = lambda: settings
    app.dependency_overrides[engine_dep] = lambda: engine
    yield engine
    app.dependency_overrides.clear()
