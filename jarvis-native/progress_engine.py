"""Preserve the agent tool loop while showing streamed text in the desktop."""

from __future__ import annotations

import asyncio
import concurrent.futures
import json
import threading


class RequestCancelled(Exception):
    pass


class ProgressEngine:
    def __init__(self, engine, cancelled):
        self.engine, self.cancelled = engine, cancelled
        self.on_text = None
        self._runner = self._future = None
        self._lock = threading.Lock()

    def __getattr__(self, name):
        return getattr(self.engine, name)

    def generate(self, messages, **kwargs):
        if self.cancelled.is_set():
            raise RequestCancelled()
        if self.on_text is None:
            result = self.engine.generate(messages, **kwargs)
            if self.cancelled.is_set():
                raise RequestCancelled()
            return result
        if self._runner is None:
            from openjarvis.engine._async_loop import AsyncLoopRunner

            self._runner = AsyncLoopRunner("jarvis-response-stream")
        future = asyncio.run_coroutine_threadsafe(
            self._collect(messages, **kwargs),
            self._runner._loop,
        )
        with self._lock:
            self._future = future
        try:
            return future.result()
        except concurrent.futures.CancelledError as exc:
            raise RequestCancelled() from exc
        finally:
            with self._lock:
                self._future = None

    async def _collect(self, messages, **kwargs):
        text, calls, usage, finish = "", {}, {}, "stop"
        self.on_text("")
        async for chunk in self.engine.stream_full(messages, **kwargs):
            if self.cancelled.is_set():
                raise RequestCancelled()
            if chunk.content:
                text += chunk.content
                self.on_text(text)
            for fragment in chunk.tool_calls or []:
                index = fragment.get("index", 0)
                call = calls.setdefault(index, {"id": "", "name": "", "arguments": ""})
                function = fragment.get("function", fragment)
                call["id"] += fragment.get("id", "")
                call["name"] += function.get("name", "")
                args = function.get("arguments", "")
                call["arguments"] += json.dumps(args) if isinstance(args, dict) else args
            if chunk.usage:
                usage = chunk.usage
            if chunk.finish_reason:
                finish = chunk.finish_reason
        return {
            "content": text,
            "tool_calls": list(calls.values()),
            "usage": usage,
            "finish_reason": finish,
            "model": kwargs.get("model", ""),
        }

    def cancel(self):
        self.cancelled.set()
        with self._lock:
            if self._future is not None:
                self._future.cancel()

    def shutdown(self):
        if self._runner is not None:
            self._runner.shutdown()
            self._runner = None
