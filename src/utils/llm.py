"""Shared async Gemini call helper with retry + exponential backoff.

Used by both the extractor and the judge so rate-limit handling lives in one place.
"""
from __future__ import annotations

import asyncio

import google.genai as genai
from google.genai import types

_TRANSIENT_MARKERS = (
    "429", "resource_exhausted", "rate limit", "quota",
    "500", "503", "internal", "unavailable", "overloaded",
    "deadline", "timeout",
)


def _is_transient(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(marker in msg for marker in _TRANSIENT_MARKERS)


async def generate_with_retry(
    client: genai.Client,
    model: str,
    contents: list,
    config: types.GenerateContentConfig,
    *,
    max_attempts: int = 5,
    base_delay: float = 4.0,
    max_delay: float = 60.0,
) -> types.GenerateContentResponse:
    """Call generate_content, retrying transient (429/5xx) failures with backoff."""
    last_exc: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return await client.aio.models.generate_content(
                model=model, contents=contents, config=config
            )
        except Exception as exc:  # noqa: BLE001 - we re-raise non-transient below
            last_exc = exc
            if attempt == max_attempts or not _is_transient(exc):
                raise
            delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
            await asyncio.sleep(delay)
    assert last_exc is not None
    raise last_exc
