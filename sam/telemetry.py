"""Lightweight request-local telemetry for Mosam classification runs."""

from __future__ import annotations

import contextvars
import threading
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class RequestTelemetry:
    request_id: str
    started_at: float = field(default_factory=time.perf_counter)
    counters: dict[str, int] = field(default_factory=dict)
    durations_ms: dict[str, float] = field(default_factory=dict)
    prompt_chars: dict[str, int] = field(default_factory=dict)
    completion_tokens: dict[str, int] = field(default_factory=dict)
    prompt_tokens: dict[str, int] = field(default_factory=dict)
    models: dict[str, set[str]] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def increment(self, name: str, amount: int = 1) -> None:
        with self._lock:
            self.counters[name] = self.counters.get(name, 0) + amount

    def record_call(
        self,
        kind: str,
        *,
        model: str | None = None,
        duration_ms: float = 0.0,
        prompt_chars: int = 0,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        success: bool = True,
    ) -> None:
        with self._lock:
            self.counters[f"{kind}_calls"] = self.counters.get(f"{kind}_calls", 0) + 1
            if not success:
                self.counters[f"{kind}_errors"] = self.counters.get(f"{kind}_errors", 0) + 1
            self.durations_ms[kind] = self.durations_ms.get(kind, 0.0) + max(duration_ms, 0.0)
            self.prompt_chars[kind] = self.prompt_chars.get(kind, 0) + max(prompt_chars, 0)
            self.prompt_tokens[kind] = self.prompt_tokens.get(kind, 0) + max(prompt_tokens, 0)
            self.completion_tokens[kind] = (
                self.completion_tokens.get(kind, 0) + max(completion_tokens, 0)
            )
            if model:
                self.models.setdefault(kind, set()).add(model)

    def total_duration_ms(self) -> float:
        return (time.perf_counter() - self.started_at) * 1000.0

    def summary(self) -> dict[str, Any]:
        with self._lock:
            return {
                "duration_ms": round(self.total_duration_ms(), 1),
                "counters": dict(sorted(self.counters.items())),
                "durations_ms": {
                    key: round(value, 1) for key, value in sorted(self.durations_ms.items())
                },
                "prompt_chars": dict(sorted(self.prompt_chars.items())),
                "prompt_tokens": dict(sorted(self.prompt_tokens.items())),
                "completion_tokens": dict(sorted(self.completion_tokens.items())),
                "models": {
                    key: sorted(value) for key, value in sorted(self.models.items())
                },
            }


_CURRENT_TELEMETRY: contextvars.ContextVar[RequestTelemetry | None] = (
    contextvars.ContextVar("mosam_request_telemetry", default=None)
)


def start_request_telemetry(request_id: str) -> tuple[RequestTelemetry, contextvars.Token]:
    telemetry = RequestTelemetry(request_id=request_id)
    token = _CURRENT_TELEMETRY.set(telemetry)
    return telemetry, token


def reset_request_telemetry(token: contextvars.Token) -> None:
    _CURRENT_TELEMETRY.reset(token)


def current_telemetry() -> RequestTelemetry | None:
    return _CURRENT_TELEMETRY.get()


def increment_telemetry(name: str, amount: int = 1) -> None:
    telemetry = current_telemetry()
    if telemetry:
        telemetry.increment(name, amount)


def record_telemetry_call(
    kind: str,
    *,
    model: str | None = None,
    duration_ms: float = 0.0,
    prompt_chars: int = 0,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    success: bool = True,
) -> None:
    telemetry = current_telemetry()
    if telemetry:
        telemetry.record_call(
            kind,
            model=model,
            duration_ms=duration_ms,
            prompt_chars=prompt_chars,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            success=success,
        )
