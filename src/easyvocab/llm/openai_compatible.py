"""Any OpenAI-compatible chat API (Fireworks, Nebius, OpenAI, vLLM, Ollama, ...)."""

import hashlib
import json
import logging
import time
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field, replace
from functools import cached_property
from typing import Any, Self

import openai
from openai import DefaultHttpxClient, OpenAI
from openai.types.chat import ChatCompletion

from easyvocab.errors import ConfigurationError, LLMError, RateLimitedError
from easyvocab.llm.pricing import FIREWORKS_PRICING
from easyvocab.models import Completion, Message, Pricing, Usage
from easyvocab.settings import Settings

logger = logging.getLogger(__name__)

FIREWORKS_BASE_URL = "https://api.fireworks.ai/inference/v1"
FIREWORKS_MODEL_PREFIX = "accounts/fireworks/models/"
NEBIUS_BASE_URL = "https://api.studio.nebius.ai/v1"
PREFLIGHT_MESSAGES = (Message("user", "Reply with OK."),)
PREFLIGHT_MAX_TOKENS = 16


@dataclass(frozen=True)
class GenerationParams:
    """Sampling parameters sent with every request (part of the cache fingerprint)."""

    temperature: float = 0.2
    max_tokens: int = 8192
    reasoning_effort: str | None = None
    extra_body: dict[str, Any] = field(default_factory=dict)


class OpenAICompatibleLLM:
    """Chat model behind an OpenAI-compatible endpoint.

    Construction never touches the network, and a missing API key is reported by
    `preflight()` (or the first call), so the object can be built in tests and notebooks.

    `http_client` lets you pass a custom client (proxies, or a mock transport in tests).

    Example:
        ```python
        llm = OpenAICompatibleLLM.fireworks("deepseek-v4p1-flash")  # reads FIREWORKS_API_KEY
        ```
    """

    def __init__(
        self,
        model: str,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        params: GenerationParams | None = None,
        pricing: Pricing | None = None,
        provider: str = "OpenAI-compatible API",
        api_key_env: str = "OPENAI_API_KEY",
        timeout: float = 120.0,
        max_retries: int = 2,
        http_client: DefaultHttpxClient | None = None,
    ) -> None:
        self._model = model
        self.api_key = api_key
        self.base_url = base_url
        self.params = params or GenerationParams()
        self.pricing = pricing
        self.provider = provider
        self.api_key_env = api_key_env
        self.timeout = timeout
        self.max_retries = max_retries
        self.http_client = http_client

    @classmethod
    def fireworks(cls, model: str, *, api_key: str | None = None, **kwargs: Any) -> Self:
        """Fireworks AI. Short names (`deepseek-v4p1-flash`) get the `accounts/fireworks/models/` prefix."""
        short_name = model.removeprefix(FIREWORKS_MODEL_PREFIX)
        kwargs.setdefault("params", GenerationParams(reasoning_effort="low"))
        kwargs.setdefault("pricing", FIREWORKS_PRICING.get(short_name))
        return cls(
            model if "/" in model else FIREWORKS_MODEL_PREFIX + model,
            api_key=api_key or Settings().key("fireworks_api_key"),
            base_url=FIREWORKS_BASE_URL,
            provider="Fireworks",
            api_key_env="FIREWORKS_API_KEY",
            **kwargs,
        )

    @classmethod
    def nebius(cls, model: str, *, api_key: str | None = None, **kwargs: Any) -> Self:
        """Nebius AI Studio."""
        return cls(
            model,
            api_key=api_key or Settings().key("nebius_api_key"),
            base_url=NEBIUS_BASE_URL,
            provider="Nebius",
            api_key_env="NEBIUS_API_KEY",
            **kwargs,
        )

    @classmethod
    def openai(cls, model: str, *, api_key: str | None = None, **kwargs: Any) -> Self:
        """OpenAI."""
        return cls(model, api_key=api_key or Settings().key("openai_api_key"), provider="OpenAI", **kwargs)

    @property
    def model(self) -> str:
        """Model identifier sent to the API."""
        return self._model

    @property
    def fingerprint(self) -> str:
        """Hash of endpoint, model and sampling params."""
        payload = {"base_url": self.base_url, "model": self._model, **asdict(self.params)}
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]

    def complete(self, messages: Sequence[Message]) -> Completion:
        """Run one chat completion and measure usage, cost and latency."""
        started = time.perf_counter()
        response = self._create(messages, self.params)
        return self._to_completion(response, time.perf_counter() - started)

    def preflight(self) -> None:
        """Check the key, then send one tiny request (catches a wrong key or model id)."""
        self._create(PREFLIGHT_MESSAGES, replace(self.params, max_tokens=PREFLIGHT_MAX_TOKENS))

    @cached_property
    def client(self) -> OpenAI:
        """The underlying OpenAI SDK client (created on first use)."""
        if not self.api_key:
            raise ConfigurationError(f"No API key for {self.provider}: set {self.api_key_env} (env or .env)")
        return OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=self.timeout,
            max_retries=self.max_retries,
            http_client=self.http_client,
        )

    def _create(self, messages: Sequence[Message], params: GenerationParams) -> ChatCompletion:
        client = self.client
        try:
            return client.chat.completions.create(**self._request(messages, params))
        except openai.AuthenticationError as exc:
            raise ConfigurationError(f"{self.provider} rejected the API key (check {self.api_key_env})") from exc
        except openai.NotFoundError as exc:
            raise ConfigurationError(f"{self.provider} doesn't know the model {self._model!r}") from exc
        except openai.RateLimitError as exc:
            raise RateLimitedError(self.provider, _retry_after(exc)) from exc
        except openai.OpenAIError as exc:
            raise LLMError(f"{self.provider} request failed: {exc}") from exc

    def _request(self, messages: Sequence[Message], params: GenerationParams) -> dict[str, Any]:
        request: dict[str, Any] = {
            "model": self._model,
            "messages": [{"role": message.role, "content": message.content} for message in messages],
            "temperature": params.temperature,
            "max_tokens": params.max_tokens,
        }
        if params.reasoning_effort:
            request["reasoning_effort"] = params.reasoning_effort
        if params.extra_body:
            request["extra_body"] = params.extra_body
        return request

    def _to_completion(self, response: ChatCompletion, latency_s: float) -> Completion:
        choice = response.choices[0]
        usage = _usage(response)
        return Completion(
            text=(choice.message.content or "").strip(),
            model=response.model or self._model,
            usage=usage,
            latency_s=latency_s,
            cost_usd=self.pricing.cost(usage) if self.pricing else None,
            finish_reason=choice.finish_reason,
        )


def _usage(response: ChatCompletion) -> Usage:
    if response.usage is None:
        return Usage()
    details = response.usage.prompt_tokens_details
    return Usage(
        prompt_tokens=response.usage.prompt_tokens,
        completion_tokens=response.usage.completion_tokens or 0,
        cached_prompt_tokens=(details.cached_tokens or 0) if details else 0,
    )


def _retry_after(exc: openai.RateLimitError) -> float | None:
    value = exc.response.headers.get("retry-after")
    try:
        return float(value) if value else None
    except ValueError:
        return None
