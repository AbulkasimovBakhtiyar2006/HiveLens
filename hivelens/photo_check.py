"""Check that an uploaded photo is what HiveLens can measure, before any analysis is spent on it.

One short Muse Spark call per photo answers: sticky board, hive frame, or something else.
A photo of something else is refused with a clear message instead of producing near-zero
measurements. The check fails open: if the call errors or the answer cannot be read, the
analysis goes ahead as before, so a model hiccup never blocks a real inspection.
"""
from __future__ import annotations

import hashlib
import json
import re

from PIL import Image

from . import config
from .meta_client import client, data_url, jpeg_bytes

PROMPT = """You check photos for a beekeeping app before analysis. Classify this photo.
"sticky_board": a white, grey or light sheet or tray that lay under a beehive to catch falling
debris and varroa mites (often with grid lines and many small brown specks).
"hive_frame": a beehive frame or a piece of honeycomb, with or without bees on it.
"other": anything else (people, animals, rooms, documents, landscapes, flowers without comb, ...).
Answer with JSON only: {"kind": "sticky_board" | "hive_frame" | "other", "why": "a few words"}"""

NAMES = {"sticky_board": "a varroa sticky board", "hive_frame": "a beehive frame or honeycomb"}


class NotHivePhoto(ValueError):
    """The photo is not a sticky board or a hive frame."""


def classify(image: Image.Image) -> dict | None:
    """{"kind", "why"} or None when the answer is unavailable."""
    small = image.convert("RGB")
    small.thumbnail((768, 768))
    key = hashlib.sha256(config.REASONING_MODEL.encode() + PROMPT.encode() + jpeg_bytes(small, 85)).hexdigest()
    path = config.CACHE_DIR / "photo_checks" / f"{key}.json"
    if path.exists():
        return json.loads(path.read_text())
    try:
        text = ""
        for budget in (1500, 4000):
            resp = client().chat.completions.create(
                model=config.REASONING_MODEL,
                messages=[{"role": "user", "content": [
                    {"type": "text", "text": PROMPT},
                    {"type": "image_url", "image_url": {"url": data_url(small, quality=85)}},
                ]}],
                reasoning_effort="low",
                max_completion_tokens=budget,
            )
            text = resp.choices[0].message.content or ""
            if text.strip():
                break
        m = re.search(r"\{.*\}", text, re.S)
        answer = json.loads(m.group(0)) if m else None
    except Exception:
        return None
    if not isinstance(answer, dict) or answer.get("kind") not in ("sticky_board", "hive_frame", "other"):
        return None
    result = {"kind": answer["kind"], "why": str(answer.get("why", ""))[:160]}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result))
    return result


def require(image: Image.Image, expected: str, label: str) -> None:
    """Raise NotHivePhoto when `image` (shown to the user as `label`) is clearly not `expected`."""
    got = classify(image)
    if not got or got["kind"] == expected:
        return
    why = f" ({got['why']})" if got.get("why") else ""
    if got["kind"] == "other":
        raise NotHivePhoto(f"The {label} does not look like {NAMES[expected]}{why}. "
                           f"HiveLens measures sticky boards and hive frames; please upload one of those.")
    raise NotHivePhoto(f"The {label} looks like {NAMES[got['kind']]}, not {NAMES[expected]}{why}. "
                       f"Add it in the {'Sticky board' if got['kind'] == 'sticky_board' else 'Frames'} section instead.")
