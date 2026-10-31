"""Пароли: argon2id; правила нового пароля (спека админ-панели §4)."""
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

_HASHER = PasswordHasher()
MIN_LENGTH = 12


def hash_password(password: str) -> str:
    return _HASHER.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _HASHER.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def problems(password: str, login: str) -> list[str]:
    out = []
    if len(password) < MIN_LENGTH:
        out.append(f"пароль короче {MIN_LENGTH} символов")
    if password.strip().lower() == login.strip().lower():
        out.append("пароль совпадает с логином")
    return out
