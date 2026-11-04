"""10-second check that your MODEL_API_KEY works for both Meta models HiveLens uses.

    python scripts/check_api.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from hivelens import config, sam  # noqa: E402
from hivelens.meta_client import client  # noqa: E402


def main() -> None:
    print(f"API base: {config.API_BASE}")
    t = time.time()
    r = client().chat.completions.create(
        model=config.REASONING_MODEL,
        messages=[{"role": "user", "content": "Reply with exactly: HiveLens online"}],
        reasoning_effort="low",
        max_completion_tokens=1000,
    )
    c = r.choices[0]
    print(f"✓ {config.REASONING_MODEL}: {c.message.content!r} (finish: {c.finish_reason}, "
          f"tokens: {getattr(r.usage, 'total_tokens', '?')}, {time.time() - t:.1f}s)")
    if not c.message.content:
        print("   empty text, raw response for debugging:")
        print("  ", r.model_dump_json(exclude_none=True)[:2000])

    img = Image.new("RGB", (512, 384), "white")
    d = ImageDraw.Draw(img)
    for x, y in [(100, 100), (300, 200), (400, 80)]:
        d.ellipse((x, y, x + 40, y + 30), fill=(120, 40, 20))
    t = time.time()
    found = sam.segment(img, "brown oval", use_cache=False)
    print(f"✓ {config.SEGMENT_MODEL}: found {len(found)} objects in a test image ({time.time() - t:.1f}s)")
    for i in found:
        print("   ", i.to_json())


if __name__ == "__main__":
    main()
