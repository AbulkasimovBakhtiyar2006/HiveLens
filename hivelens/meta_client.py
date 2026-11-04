"""Thin wrapper around the Meta Model API (https://api.meta.ai/v1).

The API is OpenAI-SDK compatible, so we use the official `openai` package with a
different base URL. Both models HiveLens calls at runtime are Meta models:
Muse Spark (reasoning, vision, tool calling) and SAM 3.1 (segmentation).
"""

from __future__ import annotations

import base64
import io
from functools import lru_cache

from PIL import Image

from . import config, usage


class MissingAPIKey(RuntimeError):
    pass


@lru_cache(maxsize=1)
def client():
    if not config.has_api_key():
        raise MissingAPIKey(
            "MODEL_API_KEY is not set. Put it in a .env file in the project root "
            "(see .env.example) or export it in your shell."
        )
    from openai import OpenAI

    options = {}
    if config.API_IPV6:
        # The locked OpenAI SDK uses httpx2. Bind only this client's connections,
        # leaving DNS and all unrelated network traffic unchanged.
        import httpx2

        options["http_client"] = httpx2.Client(
            transport=httpx2.HTTPTransport(local_address="::"), timeout=180,
        )
    c = OpenAI(base_url=config.API_BASE, api_key=config.API_KEY, timeout=180, max_retries=3, **options)
    _meter(c)
    return c


def _kind(model: str) -> str:
    return "segmentation" if model == config.SEGMENT_MODEL or "sam" in model.lower() else "reasoning"


class _MeteredStream:
    """Passes a streamed response through unchanged and records its usage when it completes."""

    def __init__(self, stream, model: str):
        self._stream = stream
        self._model = model

    def __iter__(self):
        usage_obj, done = None, False
        try:
            for event in self._stream:
                if getattr(event, "type", "") == "response.completed":
                    usage_obj = getattr(getattr(event, "response", None), "usage", None)
                    done = True
                yield event
        finally:
            usage.record(self._model, _kind(self._model), usage_obj, ok=done)

    def __getattr__(self, name):
        return getattr(self._stream, name)


def _meter(c) -> None:
    """Every Meta Model API call goes through this client, so recording here covers SAM 3.1 and Muse Spark."""
    chat_create = c.chat.completions.create
    responses_create = c.responses.create

    def metered_chat(*args, **kwargs):
        model = kwargs.get("model", config.REASONING_MODEL)
        resp = chat_create(*args, **kwargs)
        usage.record(model, _kind(model), getattr(resp, "usage", None))
        return resp

    def metered_responses(*args, **kwargs):
        model = kwargs.get("model", config.SEGMENT_MODEL)
        resp = responses_create(*args, **kwargs)
        if kwargs.get("stream"):
            return _MeteredStream(resp, model)
        usage.record(model, _kind(model), getattr(resp, "usage", None))
        return resp

    c.chat.completions.create = metered_chat
    c.responses.create = metered_responses


def resize_max_side(image: Image.Image, max_side: int | None) -> Image.Image:
    if not max_side:
        return image
    w, h = image.size
    scale = max_side / max(w, h)
    if scale >= 1:
        return image
    return image.resize((max(1, round(w * scale)), max(1, round(h * scale))), Image.LANCZOS)


def jpeg_bytes(image: Image.Image, quality: int = 90) -> bytes:
    buf = io.BytesIO()
    image.convert("RGB").save(buf, format="JPEG", quality=quality)
    return buf.getvalue()


def data_url(image: Image.Image, max_side: int | None = None, quality: int = 90) -> str:
    img = resize_max_side(image, max_side)
    return "data:image/jpeg;base64," + base64.b64encode(jpeg_bytes(img, quality)).decode()
