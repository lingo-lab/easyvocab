import json
from typing import Any

import httpx2
import pytest
from openai import DefaultHttpxClient

from easyvocab import GenerationParams, Message, OpenAICompatibleLLM, Pricing
from easyvocab.errors import ConfigurationError, LLMError, RateLimitedError

MESSAGES = [Message("system", "be nice"), Message("user", "Haus")]


def chat_response(content: str | None = '{"a": 1}') -> dict[str, Any]:
    return {
        "id": "x",
        "object": "chat.completion",
        "created": 0,
        "model": "accounts/fireworks/models/deepseek-v4p1-flash",
        "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": content}}],
        "usage": {
            "prompt_tokens": 1_000_000,
            "completion_tokens": 1_000_000,
            "total_tokens": 2_000_000,
            "prompt_tokens_details": {"cached_tokens": 500_000},
        },
    }


class FakeAPI:
    """Mock transport for the openai SDK (it uses httpx2, which respx doesn't patch)."""

    def __init__(self, status: int = 200, body: dict[str, Any] | None = None, headers: dict[str, str] | None = None):
        self.status = status
        self.body = body if body is not None else chat_response()
        self.headers = headers or {}
        self.requests: list[httpx2.Request] = []

    def handle(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        return httpx2.Response(self.status, json=self.body, headers=self.headers)

    def client(self) -> DefaultHttpxClient:
        return DefaultHttpxClient(transport=httpx2.MockTransport(self.handle))

    @property
    def last_body(self) -> dict[str, Any]:
        return json.loads(self.requests[-1].content)


def fireworks(api: FakeAPI, **kwargs: Any) -> OpenAICompatibleLLM:
    return OpenAICompatibleLLM.fireworks(
        "deepseek-v4p1-flash", api_key="test-key", max_retries=0, http_client=api.client(), **kwargs
    )


def test_complete_sends_request_and_measures_cost() -> None:
    api = FakeAPI()
    completion = fireworks(api).complete(MESSAGES)
    request = api.requests[-1]
    assert str(request.url) == "https://api.fireworks.ai/inference/v1/chat/completions"
    assert request.headers["authorization"] == "Bearer test-key"
    assert api.last_body["model"] == "accounts/fireworks/models/deepseek-v4p1-flash"
    assert api.last_body["messages"] == [{"role": "system", "content": "be nice"}, {"role": "user", "content": "Haus"}]
    assert api.last_body["reasoning_effort"] == "low"
    assert completion.text == '{"a": 1}'
    assert completion.usage.cached_prompt_tokens == 500_000
    assert completion.cost_usd == pytest.approx(0.15 + 0.003 + 1.2)  # deepseek-v4p1-flash prices
    assert completion.finish_reason == "stop"


def test_extra_body_and_empty_content() -> None:
    api = FakeAPI(body=chat_response(content=None))
    llm = fireworks(api, params=GenerationParams(extra_body={"top_k": 5}), pricing=None)
    llm.pricing = None
    completion = llm.complete(MESSAGES)
    assert api.last_body["top_k"] == 5
    assert "reasoning_effort" not in api.last_body
    assert completion.text == ""
    assert completion.cost_usd is None


@pytest.mark.parametrize(
    ("status", "error", "match"),
    [
        (401, ConfigurationError, "FIREWORKS_API_KEY"),
        (404, ConfigurationError, "doesn't know the model"),
        (429, RateLimitedError, "retry in 7s"),
        (500, LLMError, "request failed"),
    ],
)
def test_errors_are_mapped(status: int, error: type[Exception], match: str) -> None:
    api = FakeAPI(status=status, body={"error": {"message": "x"}}, headers={"retry-after": "7"})
    with pytest.raises(error, match=match):
        fireworks(api).complete(MESSAGES)


def test_missing_key_is_reported_lazily(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> None:
    monkeypatch.delenv("FIREWORKS_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)  # no .env
    llm = OpenAICompatibleLLM.fireworks("kimi-k3")
    assert llm.model == "accounts/fireworks/models/kimi-k3"
    with pytest.raises(ConfigurationError, match="set FIREWORKS_API_KEY"):
        llm.preflight()


def test_preflight_sends_a_tiny_request() -> None:
    api = FakeAPI()
    fireworks(api).preflight()
    assert api.last_body["max_tokens"] == 16


def test_fingerprint_tracks_params_and_presets() -> None:
    base = OpenAICompatibleLLM("m", api_key="k")
    assert base.fingerprint == OpenAICompatibleLLM("m", api_key="other-key").fingerprint
    assert base.fingerprint != OpenAICompatibleLLM("m", params=GenerationParams(temperature=0.9)).fingerprint
    assert OpenAICompatibleLLM.nebius("m", api_key="k").base_url == "https://api.studio.nebius.ai/v1"
    assert OpenAICompatibleLLM.openai("gpt", api_key="k").provider == "OpenAI"
    assert OpenAICompatibleLLM.fireworks("unknown-model", api_key="k").pricing is None
    assert OpenAICompatibleLLM.fireworks("x", api_key="k", pricing=Pricing(1, 1)).pricing == Pricing(1, 1)
