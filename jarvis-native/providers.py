"""Text providers using the OpenAI SDK's chat completions interface."""

from __future__ import annotations

import asyncio
import time
from collections import OrderedDict

import httpx
from openjarvis.core.registry import EngineRegistry
from openjarvis.engine._base import messages_to_dicts
from openjarvis.engine._stubs import InferenceEngine, StreamChunk

from provider_errors import ProviderBusy, retry_delay

GEMINI_MODEL = "gemini-3.5-flash-lite"


class ChatCompletionsEngine(InferenceEngine):
    is_cloud = True

    def __init__(self, *, api_key=None):
        from openai import AsyncOpenAI, OpenAI

        from credential_store import get_credential

        key = api_key or get_credential(self.key_name)
        if not key:
            raise ValueError(f"Falta {self.key_name}")
        options = dict(
            api_key=key,
            base_url=self.base_url,
            timeout=45.0,
            max_retries=0,
        )
        self._client = OpenAI(**options, http_client=httpx.Client(trust_env=False, timeout=45.0))
        self._async_options = options
        self._async_client_type = AsyncOpenAI
        self._cooldown_until = 0

    def _payload(self, messages, model, temperature, max_tokens, **kwargs):
        serialized = messages_to_dicts(messages)
        for message in serialized:
            message.pop("name", None)
            if message.pop("images", None):
                raise ValueError(f"Este adaptador de {self.provider} es solo de texto")
        return dict(
            model=model,
            messages=serialized,
            temperature=temperature,
            max_completion_tokens=max_tokens,
            **kwargs,
        )

    def generate(self, messages, *, model, temperature=0.7, max_tokens=1024, **kwargs):
        from openai import RateLimitError

        payload = self._payload(messages, model, temperature, max_tokens, **kwargs)
        for attempt in range(2):
            wait = max(0, self._cooldown_until - time.monotonic())
            if wait > 12:
                raise ProviderBusy(wait, provider=self.provider)
            if wait:
                time.sleep(wait)
            try:
                response = self._client.chat.completions.create(**payload)
                break
            except RateLimitError as exc:
                wait = retry_delay(exc) + 0.25
                self._cooldown_until = time.monotonic() + wait
                if attempt or wait > 12:
                    raise ProviderBusy(wait, provider=self.provider) from None
        if not response.choices:
            raise RuntimeError(f"{self.provider} devolvió una respuesta vacía")
        choice = response.choices[0]
        calls = self._tool_calls(choice.message.tool_calls)
        return {
            "content": choice.message.content or "",
            "model": response.model,
            "finish_reason": choice.finish_reason,
            "usage": response.usage.model_dump() if response.usage else {},
            "tool_calls": [
                {"id": call["id"], **call["function"]} for call in calls
            ],
        }

    async def stream_full(self, messages, *, model, temperature=0.7, max_tokens=1024, **kwargs):
        async with self._async_client_type(
            **self._async_options, http_client=httpx.AsyncClient(trust_env=False, timeout=45.0)
        ) as client:
            from openai import RateLimitError

            payload = self._payload(messages, model, temperature, max_tokens, **kwargs)
            for attempt in range(2):
                wait = max(0, self._cooldown_until - time.monotonic())
                if wait > 12:
                    raise ProviderBusy(wait, provider=self.provider)
                if wait:
                    await asyncio.sleep(wait)
                try:
                    stream = await client.chat.completions.create(
                        **payload, stream=True, **self.streaming_options
                    )
                    break
                except RateLimitError as exc:
                    wait = retry_delay(exc) + 0.25
                    self._cooldown_until = time.monotonic() + wait
                    if attempt or wait > 12:
                        raise ProviderBusy(wait, provider=self.provider) from None
            async with stream:
                call_indexes = {}
                async for chunk in stream:
                    choice = chunk.choices[0] if chunk.choices else None
                    calls = self._tool_calls(choice.delta.tool_calls) if choice else []
                    for call in calls:
                        if "index" not in call and call.get("id"):
                            call["index"] = call_indexes.setdefault(call["id"], len(call_indexes))
                    yield StreamChunk(
                        content=choice.delta.content if choice else None,
                        tool_calls=calls or None,
                        finish_reason=choice.finish_reason if choice else None,
                        usage=chunk.usage.model_dump() if chunk.usage else None,
                    )

    def _tool_calls(self, calls):
        return [call.model_dump(exclude_none=True) for call in calls or []]

    async def stream(self, messages, **kwargs):
        async for chunk in self.stream_full(messages, **kwargs):
            if chunk.content:
                yield chunk.content

    def health(self):
        # Credential presence is not a successful connectivity/model check.
        # Actual requests report authentication, quota and network errors.
        from credential_store import CredentialStore

        return CredentialStore().available(self.key_name)

    def can_serve(self, model):
        return model in self.list_models()

    def close(self):
        self._client.close()


class GroqEngine(ChatCompletionsEngine):
    engine_id = "groq"
    provider = "Groq"
    key_name = "GROQ_API_KEY"
    base_url = "https://api.groq.com/openai/v1"
    streaming_options = {"stream_options": {"include_usage": True}}

    def _payload(self, messages, model, temperature, max_tokens, **kwargs):
        if model.startswith("openai/gpt-oss-"):
            kwargs.setdefault("reasoning_effort", "low")
        return super()._payload(messages, model, temperature, max_tokens, **kwargs)

    def list_models(self):
        return ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.8-27b"]


class GeminiEngine(ChatCompletionsEngine):
    engine_id = "gemini"
    provider = "Gemini"
    key_name = "GEMINI_API_KEY"
    base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
    streaming_options = {}

    def __init__(self, *, api_key=None):
        super().__init__(api_key=api_key)
        self._call_signatures = OrderedDict()

    def _payload(self, messages, model, temperature, max_tokens, **kwargs):
        kwargs.setdefault("reasoning_effort", "minimal")
        payload = super()._payload(messages, model, temperature, max_tokens, **kwargs)
        for message in payload["messages"]:
            for call in message.get("tool_calls", []):
                signature = self._call_signatures.get(call["id"])
                if signature:
                    call["extra_content"] = {"google": {"thought_signature": signature}}
        return payload

    def _tool_calls(self, calls):
        serialized = super()._tool_calls(calls)
        for call in serialized:
            # Gemini requires this metadata when submitting the tool's result.
            extra = call.pop("extra_content", None) or {}
            signature = extra.get("google", {}).get("thought_signature")
            if call.get("id") and signature:
                self._call_signatures[call["id"]] = signature
                if len(self._call_signatures) > 128:
                    self._call_signatures.popitem(last=False)
        return serialized

    def list_models(self):
        return [GEMINI_MODEL]


def register_providers():
    for engine in (GroqEngine, GeminiEngine):
        if not EngineRegistry.contains(engine.engine_id):
            EngineRegistry.register_value(engine.engine_id, engine)
