"""Structured audit events for harness wrappers (zero external deps).

Enable with HARNESS_TELEMETRY=1 (JSON lines on stderr) and/or AGENT_AUDIT_LOG=<path>
(append-only JSONL file). Complements the skills' OTel guidance without forcing an
OTLP dependency on every consumer checkout.
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any


def telemetry_enabled() -> bool:
    flag = (os.environ.get("HARNESS_TELEMETRY") or "").strip().lower()
    if flag in {"1", "true", "yes", "on"}:
        return True
    return bool((os.environ.get("AGENT_AUDIT_LOG") or "").strip())


def emit_event(event: str, **fields: Any) -> None:
    """Emit one structured event when telemetry is enabled. Never raises."""
    if not telemetry_enabled():
        return
    payload: dict[str, Any] = {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "component": "platform_harness",
        "event": event,
    }
    for key, value in fields.items():
        if value is None:
            continue
        payload[key] = value
    try:
        line = json.dumps(payload, separators=(",", ":"), default=str) + "\n"
    except (TypeError, ValueError):
        return
    try:
        audit = (os.environ.get("AGENT_AUDIT_LOG") or "").strip()
        if audit:
            with open(audit, "a", encoding="utf-8") as handle:
                handle.write(line)
    except OSError:
        pass
    try:
        if (os.environ.get("HARNESS_TELEMETRY") or "").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }:
            sys.stderr.write(line)
    except OSError:
        pass


class timed_event:
    """Context manager that emits event.ok / event.error with duration_ms."""

    def __init__(self, event: str, **fields: Any) -> None:
        self.event = event
        self.fields = fields
        self._start = 0.0

    def __enter__(self) -> timed_event:
        self._start = time.monotonic()
        return self

    def __exit__(self, exc_type, exc, _tb) -> None:
        duration_ms = int((time.monotonic() - self._start) * 1000)
        if exc_type is None:
            emit_event(f"{self.event}.ok", duration_ms=duration_ms, **self.fields)
            return None
        emit_event(
            f"{self.event}.error",
            duration_ms=duration_ms,
            error_type=getattr(exc_type, "__name__", str(exc_type)),
            error=str(exc)[:500] if exc else None,
            **self.fields,
        )
        return None
