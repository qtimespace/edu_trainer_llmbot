from typing import Literal

# output_truncated — ответ обрезан лимитом вывода (finish_reason=length): не сбой провайдера, автомат не трогаем
ErrorKind = Literal["timeout", "provider_error", "rate_limit", "quota_exceeded",
                    "context_overflow", "refusal", "auth", "output_truncated"]


class ProviderError(Exception):
    def __init__(self, kind: ErrorKind, message: str = "", usage: tuple[int, int] | None = None,
                 retry_after: float | None = None):
        super().__init__(f"{kind}: {message}")
        self.kind = kind
        self.usage = usage
        self.retry_after = retry_after  # Retry-After ответа 429, секунды
