from types import SimpleNamespace

import anthropic
import httpx
import openai
import pytest
from trainer.llm_gateway.errors import ProviderError
from trainer.llm_gateway.providers.anthropic_provider import AnthropicProvider
from trainer.llm_gateway.providers.base import ProviderRequest
from trainer.llm_gateway.providers.openai_compat import OpenAICompatibleProvider

REQ = ProviderRequest(model="claude-opus-5", system="sys", user="Проверь документ", max_output_tokens=3000)


class _Endpoint:
    def __init__(self, result):
        self.result = result
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class FakeAnthropic:
    def __init__(self, result):
        self.messages = _Endpoint(result)
        self.beta = SimpleNamespace(messages=_Endpoint(result))


def anthropic_http():
    try:
        import httpx2 as h
    except ImportError:
        h = httpx
    req = h.Request("POST", "https://api.anthropic.com/v1/messages")
    return h, req


def a_status(cls, status, message="boom"):
    h, req = anthropic_http()
    return cls(message, response=h.Response(status, request=req), body=None)


def message(stop="end_turn", text='{"status": "pass"}'):
    return SimpleNamespace(
        stop_reason=stop, stop_details=None, model="claude-opus-5",
        content=[SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=text)],
        usage=SimpleNamespace(input_tokens=120, output_tokens=40),
    )


def test_anthropic_success_joins_text_blocks_only():
    client = FakeAnthropic(message())
    resp = AnthropicProvider(client).complete(REQ.model_copy(update={"effort": "medium"}))
    assert resp.text == '{"status": "pass"}'
    assert (resp.input_tokens, resp.output_tokens, resp.model) == (120, 40, "claude-opus-5")
    kw = client.messages.kwargs
    assert kw["max_tokens"] == 3000 and kw["system"] == "sys"
    assert kw["messages"] == [{"role": "user", "content": "Проверь документ"}]
    assert kw["output_config"] == {"effort": "medium"}


def test_anthropic_server_side_fallback_uses_beta_endpoint():
    client = FakeAnthropic(message())
    AnthropicProvider(client).complete(REQ.model_copy(update={"server_side_fallback": True}))
    kw = client.beta.messages.kwargs
    assert kw["betas"] == ["server-side-fallback-2026-07-01"]
    assert kw["fallbacks"] == "default"
    assert client.messages.kwargs is None


def test_anthropic_refusal_and_truncation():
    with pytest.raises(ProviderError) as e:
        AnthropicProvider(FakeAnthropic(message(stop="refusal"))).complete(REQ)
    assert e.value.kind == "refusal"
    with pytest.raises(ProviderError) as e:
        AnthropicProvider(FakeAnthropic(message(stop="max_tokens"))).complete(REQ)
    assert e.value.kind == "output_truncated" and e.value.usage == (120, 40)


@pytest.mark.parametrize("exc,kind", [
    (lambda: a_status(anthropic.RateLimitError, 429), "rate_limit"),
    (lambda: anthropic.APITimeoutError(request=anthropic_http()[1]), "timeout"),
    (lambda: a_status(anthropic.AuthenticationError, 401), "auth"),
    (lambda: a_status(anthropic.BadRequestError, 400, "prompt is too long: 1200000 tokens"), "context_overflow"),
    (lambda: a_status(anthropic.InternalServerError, 500), "provider_error"),
])
def test_anthropic_error_mapping(exc, kind):
    with pytest.raises(ProviderError) as e:
        AnthropicProvider(FakeAnthropic(exc())).complete(REQ)
    assert e.value.kind == kind


class FakeOpenAI:
    def __init__(self, result):
        self.chat = SimpleNamespace(completions=_Endpoint(result))


def completion(finish="stop", text='{"status": "warning"}'):
    return SimpleNamespace(
        model="kimi-x",
        choices=[SimpleNamespace(finish_reason=finish, message=SimpleNamespace(content=text))],
        usage=SimpleNamespace(prompt_tokens=50, completion_tokens=10),
    )


def o_status(cls, status, message="boom"):
    req = httpx.Request("POST", "https://api.example.com/v1/chat/completions")
    return cls(message, response=httpx.Response(status, request=req), body=None)


def test_openai_compat_success_and_param_name():
    client = FakeOpenAI(completion())
    p = OpenAICompatibleProvider("kimi", client=client)
    resp = p.complete(REQ.model_copy(update={"model": "kimi-x", "max_tokens_param": "max_completion_tokens"}))
    assert resp.text == '{"status": "warning"}' and resp.input_tokens == 50
    kw = client.chat.completions.kwargs
    assert kw["max_completion_tokens"] == 3000
    assert kw["messages"][0] == {"role": "system", "content": "sys"}


@pytest.mark.parametrize("exc,kind", [
    (lambda: o_status(openai.RateLimitError, 429, "insufficient_quota: out of credits"), "quota_exceeded"),
    (lambda: o_status(openai.RateLimitError, 429, "{'code': '1113', 'message': 'Insufficient balance'}"),
     "quota_exceeded"),
    (lambda: o_status(openai.RateLimitError, 429, "slow down"), "rate_limit"),
    (lambda: o_status(openai.BadRequestError, 400, "context_length_exceeded"), "context_overflow"),
    (lambda: o_status(openai.AuthenticationError, 401), "auth"),
    # OpenRouter: 402 Payment Required — на счёте нет средств или ключ упёрся в свой лимит (обсуждение #1046)
    (lambda: o_status(openai.APIStatusError, 402, "Insufficient credits"), "quota_exceeded"),
])
def test_openai_compat_error_mapping(exc, kind):
    with pytest.raises(ProviderError) as e:
        OpenAICompatibleProvider("openai", client=FakeOpenAI(exc())).complete(REQ)
    assert e.value.kind == kind


def test_openai_compat_content_filter_is_refusal():
    with pytest.raises(ProviderError) as e:
        OpenAICompatibleProvider("openai", client=FakeOpenAI(completion(finish="content_filter"))).complete(REQ)
    assert e.value.kind == "refusal"


def test_anthropic_missing_credentials_is_auth_error():
    err = TypeError('"Could not resolve authentication method. Expected one of api_key, auth_token, '
                    'or credentials to be set."')
    with pytest.raises(ProviderError) as e:
        AnthropicProvider(FakeAnthropic(err)).complete(REQ)
    assert e.value.kind == "auth"


def test_unrelated_type_error_is_not_swallowed():
    with pytest.raises(TypeError):
        AnthropicProvider(FakeAnthropic(TypeError("unexpected keyword argument 'foo'"))).complete(REQ)


def test_openai_compat_can_switch_off_reasoning():
    # прогон 2026-10-06: glm-5.3 тратил весь лимит вывода на рассуждение — Z.AI выключает его параметром thinking
    client = FakeOpenAI(completion())
    OpenAICompatibleProvider("zai", client=client).complete(REQ.model_copy(update={"thinking": False}))
    assert client.chat.completions.kwargs["extra_body"] == {"thinking": {"type": "disabled"}}
    plain = FakeOpenAI(completion())
    OpenAICompatibleProvider("kimi", client=plain).complete(REQ)
    assert "extra_body" not in plain.chat.completions.kwargs


def test_openai_compat_cut_off_answer_is_output_truncated_not_a_provider_failure():
    # #1046: OpenRouter ответил 200, ответ обрезан лимитом вывода — было «ошибка на стороне провайдера»
    with pytest.raises(ProviderError) as e:
        OpenAICompatibleProvider("openai", client=FakeOpenAI(completion(finish="length"))).complete(REQ)
    assert e.value.kind == "output_truncated"


def test_a_429_carries_the_retry_after_of_the_response():
    req = httpx.Request("POST", "https://api.example.com/v1/chat/completions")
    err = openai.RateLimitError("slow down", response=httpx.Response(429, request=req, headers={"retry-after": "7"}),
                                body=None)
    with pytest.raises(ProviderError) as e:
        OpenAICompatibleProvider("kimi", client=FakeOpenAI(err)).complete(REQ)
    assert e.value.kind == "rate_limit" and e.value.retry_after == 7
    h, areq = anthropic_http()
    aerr = anthropic.RateLimitError("slow", response=h.Response(429, request=areq, headers={"retry-after": "12"}),
                                    body=None)
    with pytest.raises(ProviderError) as e:
        AnthropicProvider(FakeAnthropic(aerr)).complete(REQ)
    assert e.value.retry_after == 12
