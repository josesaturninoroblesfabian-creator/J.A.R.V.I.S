"""Groq adapter using the already installed OpenAI SDK and OpenJarvis types."""

from __future__ import annotations

import asyncio
import time

import httpx
from openjarvis.core.registry import EngineRegistry
from openjarvis.engine._base import messages_to_dicts
from openjarvis.engine._stubs import InferenceEngine, StreamChunk

from provider_errors import ProviderBusy, retry_delay


class GroqEngine(InferenceEngine):
    engine_id = "groq"
    is_cloud = True

    def __init__(self, *, api_key=None):
        from openai import AsyncOpenAI, OpenAI

        from credential_store import get_credential

        key = api_key or get_credential("GROQ_API_KEY")
        if not key:
            raise ValueError("Falta GROQ_API_KEY")
        options = dict(
            api_key=key,
            base_url="https://api.groq.com/openai/v1",
            timeout=45.0,
            max_retries=0,
        )
        self._client = OpenAI(**options, http_client=httpx.Client(trust_env=False, timeout=45.0))
        self._async_options = options
        self._async_client_type = AsyncOpenAI
        self._cooldown_until = 0

    @staticmethod
    def _payload(messages, model, temperature, max_tokens, **kwargs):
        serialized = messages_to_dicts(messages)
        for message in serialized:
            message.pop("name", None)  # Not accepted by Groq.
            if message.pop("images", None):
                raise ValueError("Este adaptador Groq es solo de texto")
        if model.startswith("openai/gpt-oss-"):
            kwargs.setdefault("reasoning_effort", "low")
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
                raise ProviderBusy(wait)
            if wait:
                time.sleep(wait)
            try:
                response = self._client.chat.completions.create(**payload)
                break
            except RateLimitError as exc:
                wait = retry_delay(exc) + 0.25
                self._cooldown_until = time.monotonic() + wait
                if attempt or wait > 12:
                    raise ProviderBusy(wait) from None
        if not response.choices:
            raise RuntimeError("Groq devolvió una respuesta vacía")
        choice = response.choices[0]
        return {
            "content": choice.message.content or "",
            "model": response.model,
            "finish_reason": choice.finish_reason,
            "usage": response.usage.model_dump() if response.usage else {},
            "tool_calls": [
                {"id": tc.id, "name": tc.function.name, "arguments": tc.function.arguments}
                for tc in choice.message.tool_calls or []
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
                    raise ProviderBusy(wait)
                if wait:
                    await asyncio.sleep(wait)
                try:
                    stream = await client.chat.completions.create(
                        **payload, stream=True, stream_options={"include_usage": True}
                    )
                    break
                except RateLimitError as exc:
                    wait = retry_delay(exc) + 0.25
                    self._cooldown_until = time.monotonic() + wait
                    if attempt or wait > 12:
                        raise ProviderBusy(wait) from None
            async with stream:
                async for chunk in stream:
                    choice = chunk.choices[0] if chunk.choices else None
                    yield StreamChunk(
                        content=choice.delta.content if choice else None,
                        tool_calls=[
                            tc.model_dump(exclude_none=True) for tc in choice.delta.tool_calls or []
                        ]
                        if choice
                        else None,
                        finish_reason=choice.finish_reason if choice else None,
                        usage=chunk.usage.model_dump() if chunk.usage else None,
                    )

    async def stream(self, messages, **kwargs):
        async for chunk in self.stream_full(messages, **kwargs):
            if chunk.content:
                yield chunk.content

    def list_models(self):
        return ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.8-27b"]

    def health(self):
        # Credential presence is not a successful connectivity/model check.
        # Actual requests report authentication, quota and network errors.
        from credential_store import CredentialStore

        return CredentialStore().available("GROQ_API_KEY")

    def can_serve(self, model):
        return model in self.list_models()

    def close(self):
        self._client.close()


def register_providers():
    if not EngineRegistry.contains("groq"):
        EngineRegistry.register_value("groq", GroqEngine)
