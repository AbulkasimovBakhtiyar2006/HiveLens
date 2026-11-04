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

from . import config


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

    return OpenAI(base_url=config.API_BASE, api_key=config.API_KEY, timeout=180, max_retries=3)


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
