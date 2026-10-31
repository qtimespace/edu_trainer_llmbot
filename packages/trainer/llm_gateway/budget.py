import math


def estimate_tokens(text: str) -> int:
    """Грубая верхняя оценка: ~3 символа на токен (кириллица дороже латиницы)."""
    return math.ceil(len(text) / 3)


class BudgetTracker:
    def __init__(self, max_usd: float):
        self.max_usd = max_usd
        self.spent = 0.0
        self._reserved = 0.0

    def reserve(self, amount: float) -> bool:
        if self.spent + self._reserved + amount > self.max_usd + 1e-12:
            return False
        self._reserved += amount
        return True

    def settle(self, reserved: float, actual: float) -> None:
        self._reserved -= reserved
        self.spent += actual

    @property
    def remaining(self) -> float:
        return self.max_usd - self.spent - self._reserved
