import os
import re

import openai

from trainer.llm_gateway.errors import ProviderError

from .base import ProviderRequest, ProviderResponse

_QUOTA = re.compile(r"insufficient_quota|insufficient balance|'1113'", re.IGNORECASE)


def _retry_after(e) -> float | None:
    from trainer.llm_gateway.limits import retry_after_seconds
    response = getattr(e, "response", None)
    return retry_after_seconds(response.headers.get("retry-after") if response is not None else None)


class OpenAICompatibleProvider:
    """OpenAI и OpenAI-совместимые endpoint'ы (Kimi/Moonshot) через официальный SDK `openai`."""

    def __init__(self, name: str, client=None, base_url: str | None = None, api_key_env: str | None = None,
                 api_key: str | None = None):
        self.name = name
        if client is None:
            key = api_key or (os.environ.get(api_key_env) if api_key_env else None)
            client = openai.OpenAI(api_key=key, base_url=base_url, max_retries=0)
        self._client = client

    def complete(self, request: ProviderRequest) -> ProviderResponse:
        kwargs = {
            "model": request.model,
            "messages": [{"role": "system", "content": request.system},
                         {"role": "user", "content": request.user}],
            request.max_tokens_param: request.max_output_tokens,
        }
        if request.thinking is not None:  # Z.AI (glm): {"thinking": {"type": "enabled" | "disabled"}}
            kwargs["extra_body"] = {"thinking": {"type": "enabled" if request.thinking else "disabled"}}
        try:
            resp = self._client.chat.completions.create(**kwargs)
        except openai.RateLimitError as e:
            # OpenAI шлёт insufficient_quota, Z.AI — 429 с кодом 1113 «Insufficient balance».
            kind = "quota_exceeded" if _QUOTA.search(str(e)) else "rate_limit"
            raise ProviderError(kind, str(e), retry_after=_retry_after(e)) from e
        except openai.APITimeoutError as e:
            raise ProviderError("timeout", str(e)) from e
        except (openai.AuthenticationError, openai.PermissionDeniedError) as e:
            raise ProviderError("auth", str(e)) from e
        except openai.BadRequestError as e:
            text = str(e).lower()
            kind = "context_overflow" if "context_length" in text or "maximum context" in text else "provider_error"
            raise ProviderError(kind, str(e)) from e
        except openai.APIStatusError as e:
            # 402 Payment Required (OpenRouter): нет средств на счёте или ключ упёрся в свой лимит — свойство ключа
            kind = "quota_exceeded" if getattr(e, "status_code", None) == 402 else "provider_error"
            raise ProviderError(kind, str(e)) from e
        except openai.APIConnectionError as e:
            raise ProviderError("provider_error", str(e)) from e

        choice = resp.choices[0]
        usage = (resp.usage.prompt_tokens, resp.usage.completion_tokens)
        if choice.finish_reason == "content_filter":
            raise ProviderError("refusal", "content_filter", usage)
        if choice.finish_reason == "length":
            raise ProviderError("output_truncated", "output truncated at max tokens", usage)
        return ProviderResponse(text=choice.message.content or "", input_tokens=usage[0],
                                output_tokens=usage[1], model=resp.model)
