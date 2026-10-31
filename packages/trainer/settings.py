from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_PKG = Path(__file__).resolve().parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TRAINER_", env_file=".env", env_file_encoding="utf-8",
                                      extra="ignore", populate_by_name=True)

    database_url: str = "postgresql+psycopg://trainer:trainer@localhost:5432/trainer"
    # ключи шифрования ключей LLM: "kid1:<base64 32 байта>,kid2:…", первый — активный; пусто — 503
    secrets_keys: str = ""
    session_cookie_secure: bool = True  # cookie только по HTTPS; в локальной разработке — false
    # преподаватель: создаётся/синхронизируется при старте API
    teacher_login: str = ""
    teacher_password: str = Field(default="", repr=False)
    # origin панели (проверка Origin у WebSocket терминала)
    public_origin: str = "http://localhost:3000"

    docker_url: str = "unix:///var/run/docker.sock"
    sandbox_image: str = "trainer-sandbox:1"
    sandbox_network: str = "trainer-sandbox"
    sandbox_mem: str = "384m"
    sandbox_cpus: float = 0.5
    sandbox_pids: int = 256
    # "docker" — настоящие контейнеры; "fake" — заглушка для разработки без Docker
    sandbox_backend: str = "docker"

    llm_registry_path: Path = _PKG / "llm_gateway" / "registry.yaml"
    llm_policies_dir: Path = _PKG / "llm_gateway" / "policies"


@lru_cache
def get_settings() -> Settings:
    return Settings()
