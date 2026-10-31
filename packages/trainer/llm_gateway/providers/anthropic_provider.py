import anthropic

from trainer.llm_gateway.errors import ProviderError

from .base import ProviderRequest, ProviderResponse

SERVER_FALLBACK_BETA = "server-side-fallback-2026-07-01"


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, client=None, api_key: str | None = None, base_url: str | None = None):
        # Повторы и fallback решает Execution Engine, поэтому встроенные ретраи SDK выключены.
        self._client = client if client is not None else anthropic.Anthropic(
            api_key=api_key or None, base_url=base_url or None, max_retries=0)

    def complete(self, request: ProviderRequest) -> ProviderResponse:
        kwargs = {
            "model": request.model,
            "max_tokens": request.max_output_tokens,
            "system": request.system,
            "messages": [{"role": "user", "content": request.user}],
        }
        if request.effort:
            kwargs["output_config"] = {"effort": request.effort}
        try:
            if request.server_side_fallback:
                resp = self._client.beta.messages.create(
                    betas=[SERVER_FALLBACK_BETA], fallbacks="default", **kwargs)
            else:
                resp = self._client.messages.create(**kwargs)
        except anthropic.RateLimitError as e:
            from trainer.llm_gateway.limits import retry_after_seconds
            response = getattr(e, "response", None)
            raise ProviderError("rate_limit", str(e), retry_after=retry_after_seconds(
                response.headers.get("retry-after") if response is not None else None)) from e
        except anthropic.APITimeoutError as e:
            raise ProviderError("timeout", str(e)) from e
        except (anthropic.AuthenticationError, anthropic.PermissionDeniedError) as e:
            raise ProviderError("auth", str(e)) from e
        except anthropic.BadRequestError as e:
            kind = "context_overflow" if "too long" in str(e).lower() else "provider_error"
            raise ProviderError(kind, str(e)) from e
        except anthropic.APIStatusError as e:
            raise ProviderError("provider_error", str(e)) from e
        except anthropic.APIConnectionError as e:
            raise ProviderError("provider_error", str(e)) from e
        except TypeError as e:
            # Без учётных данных SDK бросает TypeError до запроса; прочие TypeError — ошибки кода.
            if "Could not resolve authentication method" not in str(e):
                raise
            raise ProviderError("auth", "no Anthropic credentials configured") from e

        usage = (resp.usage.input_tokens, resp.usage.output_tokens)
        if resp.stop_reason == "refusal":
            category = getattr(resp.stop_details, "category", None) if resp.stop_details else None
            raise ProviderError("refusal", f"category={category}", usage)
        if resp.stop_reason == "max_tokens":
            raise ProviderError("output_truncated", "output truncated at max_tokens", usage)
        text = "".join(b.text for b in resp.content if b.type == "text")
        return ProviderResponse(text=text, input_tokens=usage[0], output_tokens=usage[1], model=resp.model)
