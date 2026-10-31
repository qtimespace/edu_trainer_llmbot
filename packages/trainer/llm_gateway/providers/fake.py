from trainer.llm_gateway.errors import ProviderError

from .base import ProviderRequest, ProviderResponse


class FakeProvider:
    """Сценарный провайдер для тестов и офлайн-прогонов: отдаёт ответы/ошибки по очереди."""

    def __init__(self, name: str, script: list[ProviderResponse | ProviderError]):
        self.name = name
        self._script = list(script)
        self.calls: list[ProviderRequest] = []

    def complete(self, request: ProviderRequest) -> ProviderResponse:
        self.calls.append(request)
        if not self._script:
            raise AssertionError(f"FakeProvider {self.name}: script exhausted")
        item = self._script.pop(0)
        if isinstance(item, ProviderError):
            raise item
        return item
