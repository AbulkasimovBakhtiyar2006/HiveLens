"""Muse Spark as a second pair of eyes on the sticky board.

Every dark, mite-sized spot that SAM 3.1 did not recognise is cut out, the cut-outs
are laid out on numbered contact sheets (36 per sheet), and Muse Spark is asked which
numbers show a varroa mite. A "yes" is still not a count: the measurement engine
checks each voted spot for mite size and colour before it is counted.
"""

from __future__ import annotations

import hashlib
import json
import re

from PIL import Image, ImageDraw

from . import config
from .meta_client import client, data_url, jpeg_bytes

TILE = 128   # px of each cut-out on the sheet
COLS = 6     # 6 x 6 = 36 cut-outs per sheet
PROMPT = """Each numbered tile is a close-up of a sticky board that was under a beehive.
Which tiles show a varroa mite? A varroa mite is a flat, reddish-brown, shiny oval about
1.1 x 1.6 mm (in these tiles roughly a fifth to a third of the tile wide), wider than long,
sometimes with tiny legs along one edge. Do NOT count: yellow or orange wax crumbs, pollen,
irregular debris, black or greenish insect fragments, dead bees, shadows, or dirt on a grey
background.
Answer with JSON only: {"mites": [tile numbers]}  (an empty list if none)."""


def _sheet(board: Image.Image, centers: list[tuple[float, float]], first: int, zoom: float = 1.0) -> Image.Image:
    w = board.size[0]
    half = max(16, int(0.0132 * w / zoom))  # ~80 px window on a 6048 px wide photo (zoom 1)
    rows = (len(centers) + COLS - 1) // COLS
    sheet = Image.new("RGB", (COLS * TILE, rows * TILE), "white")
    d = ImageDraw.Draw(sheet)
    for k, (cx, cy) in enumerate(centers):
        crop = board.crop((int(cx - half), int(cy - half), int(cx + half), int(cy + half))).resize((TILE, TILE))
        x, y = (k % COLS) * TILE, (k // COLS) * TILE
        sheet.paste(crop, (x, y))
        d.rectangle((x, y, x + 26, y + 16), fill="black")
        d.text((x + 3, y + 2), str(first + k), fill="white")
        d.rectangle((x, y, x + TILE - 1, y + TILE - 1), outline="white")
    return sheet


def _ask(sheet: Image.Image) -> list[int]:
    key = hashlib.sha256(config.REASONING_MODEL.encode() + PROMPT.encode() + jpeg_bytes(sheet, 90)).hexdigest()
    path = config.CACHE_DIR / "muse_votes" / f"{key}.json"
    if path.exists():
        cached = json.loads(path.read_text())
        if cached.get("raw", "").strip():  # an empty answer is a failed call, not "no mites": ask again
            return cached["mites"]
    # The model sometimes returns no content at all (12% of cached sheets did), which used to be
    # read as "no mites" and wiped out whole boards. Retry with a larger budget; never cache a blank.
    text, finish = "", None
    for budget in (2000, 4000, 8000):
        resp = client().chat.completions.create(
            model=config.REASONING_MODEL,
            messages=[{"role": "user", "content": [
                {"type": "text", "text": PROMPT},
                {"type": "image_url", "image_url": {"url": data_url(sheet, quality=90)}},
            ]}],
            reasoning_effort="low",
            max_completion_tokens=budget,
        )
        text = resp.choices[0].message.content or ""
        finish = resp.choices[0].finish_reason
        if re.search(r"\[([\d,\s]*)\]", text):
            break
    m = re.search(r"\[([\d,\s]*)\]", text)
    if not m:  # don't fail the whole inspection, but don't cache it either: next run asks again
        import sys
        print(f"WARNING: Muse Spark gave no usable answer for a contact sheet (finish_reason={finish})",
              file=sys.stderr)
        return []
    mites = [int(x) for x in re.findall(r"\d+", m.group(1))]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"mites": mites, "raw": text, "finish_reason": finish}))
    return mites


def vote_mites(board: Image.Image, centers: list[tuple[float, float]], progress=None) -> list[int]:
    """Returns indices into `centers` that Muse Spark calls a varroa mite.

    (A second, zoomed look with a union of votes was tested on 12 boards and lowered
    F1 from ~0.82 to 0.72, so there is one look.)"""
    from concurrent.futures import ThreadPoolExecutor

    per = COLS * COLS
    chunks = [(i, centers[i: i + per]) for i in range(0, len(centers), per)]
    yes: list[int] = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(_ask, _sheet(board, chunk, first + 1)) for first, chunk in chunks]
        for n, fut in enumerate(futures, 1):
            yes += fut.result()
            if progress:
                progress(n, len(futures))
    return sorted({k - 1 for k in yes if 1 <= k <= len(centers)})


# ── comb tiles ────────────────────────────────────────────────────────────────

TILE_PROMPT = """Each numbered tile is a piece of a honey bee frame (comb).
Label each tile with the content covering most of it:
H = capped honey (flat, pale white or light-yellow wax caps, often glossy)
B = capped brood (matte tan / light-brown, slightly domed caps)
L = open brood (white larvae or eggs visible in open cells)
P = pollen (cells packed with yellow, orange or red pollen)
N = nectar or empty cells (open cells, shiny liquid or empty dark bottoms)
X = cannot tell (covered by bees, wood, blur, not comb)
Answer with JSON only, every tile number as a key, e.g. {"1": "H", "2": "B"}."""


def _ask_tiles(sheet: Image.Image, n: int) -> dict[int, str]:
    key = hashlib.sha256(config.REASONING_MODEL.encode() + TILE_PROMPT.encode() + jpeg_bytes(sheet, 90)).hexdigest()
    path = config.CACHE_DIR / "muse_tiles" / f"{key}.json"
    if path.exists():
        raw = json.loads(path.read_text())["raw"]
    else:
        resp = client().chat.completions.create(
            model=config.REASONING_MODEL,
            messages=[{"role": "user", "content": [
                {"type": "text", "text": TILE_PROMPT},
                {"type": "image_url", "image_url": {"url": data_url(sheet, quality=90)}},
            ]}],
            reasoning_effort="low",
            max_completion_tokens=3000,
        )
        raw = resp.choices[0].message.content or ""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"raw": raw}))
    out = {}
    for num, lab in re.findall(r'"?(\d+)"?\s*:\s*"?([HBLPNX])"?', raw.upper()):
        k = int(num)
        if 1 <= k <= n:
            out[k] = lab
    return out


def label_tiles(frame: Image.Image, rects: list[tuple[float, float, float, float]], tile_px: int = 160) -> dict[int, str]:
    """Labels comb tiles (rectangles in image px) with H/B/L/P/N/X. Keys are indices into `rects`."""
    from concurrent.futures import ThreadPoolExecutor

    per = COLS * COLS
    jobs = []
    for first in range(0, len(rects), per):
        chunk = rects[first: first + per]
        rows = (len(chunk) + COLS - 1) // COLS
        sheet = Image.new("RGB", (COLS * tile_px, rows * tile_px), "white")
        d = ImageDraw.Draw(sheet)
        for k, r in enumerate(chunk):
            crop = frame.crop(tuple(int(v) for v in r)).resize((tile_px, tile_px))
            x, y = (k % COLS) * tile_px, (k // COLS) * tile_px
            sheet.paste(crop, (x, y))
            d.rectangle((x, y, x + 26, y + 16), fill="black")
            d.text((x + 3, y + 2), str(k + 1), fill="white")
            d.rectangle((x, y, x + tile_px - 1, y + tile_px - 1), outline="white")
        jobs.append((first, sheet, len(chunk)))
    labels: dict[int, str] = {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        futs = [(first, pool.submit(_ask_tiles, sheet, n)) for first, sheet, n in jobs]
        for first, fut in futs:
            for k, lab in fut.result().items():
                labels[first + k - 1] = lab
    return labels
