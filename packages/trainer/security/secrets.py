"""Шифрование личных доступов (спека 3.0a §4): AES-256-GCM, формат enc:v1:<kid>:<b64(nonce‖ct)>, AAD строки."""
import base64
import binascii
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

PREFIX = "enc:v1:"
_NONCE = 12


class SecretError(Exception):
    """Секрет не расшифровывается: чужая строка, удалённый ключ или повреждение."""


class VaultNotConfigured(Exception):
    """Нет DOCOPS_SECRETS_KEYS — запасного ключа нет сознательно."""


class SecretBox:
    def __init__(self, keys: dict[str, bytes], active: str):
        if active not in keys:
            raise ValueError(f"активный ключ {active} не задан")
        for kid, key in keys.items():
            if len(key) != 32:
                raise ValueError(f"ключ {kid}: нужно 32 байта")
        self._keys = dict(keys)
        self.active = active

    @classmethod
    def from_spec(cls, spec: str) -> "SecretBox | None":
        items = [p.strip() for p in (spec or "").split(",") if p.strip()]
        if not items:
            return None
        keys: dict[str, bytes] = {}
        for item in items:
            kid, sep, b64 = item.partition(":")
            if not sep or not kid:
                raise ValueError("DOCOPS_SECRETS_KEYS: формат kid:base64[,kid:base64]")
            try:
                keys[kid] = base64.b64decode(b64, validate=True)
            except (binascii.Error, ValueError) as e:
                raise ValueError(f"ключ {kid}: не base64") from e
        return cls(keys, items[0].partition(":")[0])

    def encrypt(self, plain: str, aad: str) -> str:
        nonce = os.urandom(_NONCE)
        ct = AESGCM(self._keys[self.active]).encrypt(nonce, plain.encode("utf-8"), aad.encode("utf-8"))
        return f"{PREFIX}{self.active}:{base64.b64encode(nonce + ct).decode()}"

    @staticmethod
    def kid_of(token: str) -> str | None:
        if not token.startswith(PREFIX):
            return None
        return token[len(PREFIX):].partition(":")[0] or None

    def decrypt(self, token: str, aad: str) -> str:
        kid = self.kid_of(token)
        key = self._keys.get(kid or "")
        if key is None:
            raise SecretError(f"ключ {kid!r} не найден или формат неизвестен")
        try:
            raw = base64.b64decode(token[len(PREFIX) + len(kid) + 1:], validate=True)
            return AESGCM(key).decrypt(raw[:_NONCE], raw[_NONCE:], aad.encode("utf-8")).decode("utf-8")
        except (InvalidTag, binascii.Error, ValueError) as e:
            raise SecretError("секрет не расшифровывается") from e
