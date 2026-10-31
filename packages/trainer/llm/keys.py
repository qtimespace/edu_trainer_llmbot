"""Ключи провайдеров LLM преподавателя: в БД только шифротекст (AES-GCM), наружу — только «задан/не задан»."""
from sqlalchemy import Engine, text

from trainer.security.secrets import SecretBox, VaultNotConfigured

PROVIDERS = ("openrouter", "hf")


class LlmKeyStore:
    def __init__(self, engine: Engine, box: SecretBox | None):
        self._engine, self._box = engine, box

    def _need_box(self) -> SecretBox:
        if self._box is None:
            raise VaultNotConfigured("не задан TRAINER_SECRETS_KEYS — ключи LLM хранить нельзя")
        return self._box

    @staticmethod
    def _check(provider: str) -> None:
        if provider not in PROVIDERS:
            raise ValueError(f"провайдер {provider} не поддерживается: {', '.join(PROVIDERS)}")

    def set(self, provider: str, key: str) -> None:
        self._check(provider)
        token = self._need_box().encrypt(key.strip(), aad=f"llm|{provider}")
        with self._engine.begin() as c:
            c.execute(text("""INSERT INTO llm_keys (provider, secret) VALUES (:p, :s)
                              ON CONFLICT (provider) DO UPDATE SET secret = EXCLUDED.secret, updated_at = now()"""),
                      {"p": provider, "s": token})

    def get(self, provider: str) -> str | None:
        with self._engine.connect() as c:
            token = c.execute(text("SELECT secret FROM llm_keys WHERE provider = :p"), {"p": provider}).scalar()
        return self._need_box().decrypt(token, aad=f"llm|{provider}") if token else None

    def status(self) -> dict[str, bool]:
        with self._engine.connect() as c:
            have = {r.provider for r in c.execute(text("SELECT provider FROM llm_keys"))}
        return {p: p in have for p in PROVIDERS}

    def delete(self, provider: str) -> None:
        with self._engine.begin() as c:
            c.execute(text("DELETE FROM llm_keys WHERE provider = :p"), {"p": provider})
