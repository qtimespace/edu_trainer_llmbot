from typing import Protocol

from pydantic import BaseModel


class ProviderRequest(BaseModel):
    model: str
    system: str
    user: str
    max_output_tokens: int
    server_side_fallback: bool = False
    effort: str | None = None
    max_tokens_param: str = "max_tokens"
    thinking: bool | None = None


class ProviderResponse(BaseModel):
    text: str
    input_tokens: int
    output_tokens: int
    model: str


class Provider(Protocol):
    name: str

    def complete(self, request: ProviderRequest) -> ProviderResponse: ...
