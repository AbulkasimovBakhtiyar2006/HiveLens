"""Side-by-side evidence for the demo: Meta models used naively vs. the HiveLens pipeline.

    python scripts/demo_assets.py                     # board IMG_5582 + every photo in data/demo/comb/
    python scripts/demo_assets.py --board IMG_5651 --frames 0

Everything is a real run (SAM/Muse answers are cached, so re-runs are free):
  naive SAM 3.1    one call on the whole board ("varroa mite"), like any first try
  naive Muse Spark the whole board photo, "how many varroa mites?"
  naive SAM comb   "capped brood" / "capped honey" on the whole frame
  HiveLens         the full pipeline (grid + 300 px re-check + Muse vote + physical checks)
Writes data/demo_assets/: comparison images, the evidence sheet, Muse's contact sheets and numbers.json.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from hivelens import config, measure, sam, viz  # noqa: E402
from hivelens.meta_client import client, data_url, jpeg_bytes, resize_max_side  # noqa: E402

Image.MAX_IMAGE_PIXELS = None
OUT = config.DATA_DIR / "demo_assets"
YELLOW = (245, 190, 20)
NAIVE_MUSE_PROMPT = ("This is a photo of a sticky board that was under a beehive for a few days. "
                     "How many varroa mites are on it? Answer with JSON only: {\"count\": <number>}")
NAIVE_COMB = {"brood": "capped brood cells", "honey": "capped honey cells"}


def expert_boxes(stem: str) -> list[tuple[float, float, float, float]]:
    xml = next((config.DATA_DIR / "varroa").rglob(stem + ".xml"))
    out = []
    for obj in ET.parse(xml).getroot().iter("object"):
        b = obj.find("bndbox")
        out.append(tuple(float(b.find(k).text) for k in ("xmin", "ymin", "xmax", "ymax")))
    return out


def naive_muse_count(board: Image.Image) -> tuple[int | None, str]:
    small = resize_max_side(board, 2048)
    key = hashlib.sha256(config.REASONING_MODEL.encode() + NAIVE_MUSE_PROMPT.encode() + jpeg_bytes(small, 90)).hexdigest()
    path = config.CACHE_DIR / "naive_muse" / f"{key}.json"
    if path.exists():
        raw = json.loads(path.read_text())["raw"]
    else:
        resp = client().chat.completions.create(
            model=config.REASONING_MODEL,
            messages=[{"role": "user", "content": [
                {"type": "text", "text": NAIVE_MUSE_PROMPT},
                {"type": "image_url", "image_url": {"url": data_url(small, quality=90)}},
            ]}],
            reasoning_effort="low",
            max_completion_tokens=2000,
        )
        raw = resp.choices[0].message.content or ""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"raw": raw}))
    m = re.search(r'"count"\s*:\s*(\d+)', raw)
    return (int(m.group(1)) if m else None), raw


def _panel(img: Image.Image, w: int, h: int) -> tuple[Image.Image, float]:
    s = min(w / img.size[0], h / img.size[1])
    return img.resize((round(img.size[0] * s), round(img.size[1] * s)), Image.LANCZOS), s


def _canvas(title: str, sub: str) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    c = Image.new("RGB", (1920, 1080), (248, 247, 244))
    d = ImageDraw.Draw(c)
    d.text((40, 26), title, fill=(20, 20, 20), font=viz._font(40))
    d.text((40, 80), sub, fill=(90, 90, 90), font=viz._font(22))
    return c, d


def _inset_box(board, hl, naive, side=1000):
    """A square region with the most counted mites (same region on both sides)."""
    pts = [i.center for i in hl.kept] or [i.center for i in naive] or [(board.size[0] / 2, board.size[1] / 2)]
    best = max(pts, key=lambda p: sum(abs(p[0] - q[0]) < side / 2 and abs(p[1] - q[1]) < side / 2 for q in pts))
    x0 = int(min(max(best[0] - side / 2, 0), board.size[0] - side))
    y0 = int(min(max(best[1] - side / 2, 0), board.size[1] - side))
    return x0, y0, x0 + side, y0 + side


def board_comparison(board, stem, naive, hl, expert, muse_n):
    c, d = _canvas(f"Same board ({stem}), same Meta models",
                   f"Expert annotation: {len(expert)} mites on a {board.size[0]}×{board.size[1]} px photo · right of each board: zoom on the marked square")
    box = _inset_box(board, hl, naive)
    y0 = 140
    sides = [
        (40, "SAM 3.1 out of the box", "whole photo, one call", YELLOW,
         [(i.center, YELLOW) for i in naive], f"{len(naive)} found"),
        (980, "HiveLens", "SAM grid + re-check, Muse vote, checks", viz.GREEN,
         [(i.center, viz.BLUE if "Muse" in i.concept else viz.GREEN) for i in hl.kept], f"{hl.count} counted"),
    ]
    for x0, label, how, color, marks, big in sides:
        p, s = _panel(board, 560, 860)
        z = 340
        arr = np.array(p)
        for (cx, cy), col in marks:
            cv2.circle(arr, (int(cx * s), int(cy * s)), 9, col, 2)
        bx = tuple(int(v * s) for v in box)
        cv2.rectangle(arr, bx[:2], bx[2:], (20, 20, 20), 2)
        c.paste(Image.fromarray(arr), (x0, y0))
        d.rectangle((x0, y0, x0 + p.size[0], y0 + p.size[1]), outline=color, width=4)
        # zoom
        zs = z / (box[2] - box[0])
        zarr = np.array(board.crop(box).resize((z, z), Image.LANCZOS))
        for (cx, cy), col in marks:
            if box[0] <= cx < box[2] and box[1] <= cy < box[3]:
                cv2.circle(zarr, (int((cx - box[0]) * zs), int((cy - box[1]) * zs)), 14, col, 3)
        zx = x0 + p.size[0] + 20
        c.paste(Image.fromarray(zarr), (zx, y0))
        d.rectangle((zx, y0, zx + z, y0 + z), outline=(20, 20, 20), width=2)
        d.text((zx, y0 + z + 24), label, fill=(30, 30, 30), font=viz._font(30))
        d.text((zx, y0 + z + 62), viz._fit_text(d, how, viz._font(17), 1920 - zx - 10), fill=(90, 90, 90), font=viz._font(17))
        d.text((zx, y0 + z + 100), big, fill=color, font=viz._font(58))
    d.text((40, 1030), f"Muse Spark alone (whole photo, \"how many varroa mites?\"): "
                       f"{muse_n if muse_n is not None else 'no number given'}   ·   expert: {len(expert)}",
           fill=(70, 70, 70), font=viz._font(22))
    return c


def comb_comparison(frame, name, naive_pct, naive_maps, res):
    c, d = _canvas(f"Same frame ({name}), same Meta models",
                   "Left: SAM 3.1 prompted with a cell type. Right: SAM 3.1 outlines comb and bees, Muse Spark labels each tile")
    pw, ph, y0 = 900, 640, 150
    # left: naive masks
    scale, shape = measure._canvas(frame.size)
    small = cv2.resize(np.array(frame), (shape[1], shape[0]), interpolation=cv2.INTER_AREA)
    tint = small.copy()
    tint[naive_maps["brood"]] = viz.CLASS_COLORS["brood"]
    tint[naive_maps["honey"]] = viz.CLASS_COLORS["honey"]
    left = Image.fromarray(cv2.addWeighted(small, 0.5, tint, 0.5, 0))
    right = viz.comb_overlay(frame, res)
    f = res.fractions
    texts = [
        ("SAM 3.1 out of the box: \"capped brood cells\", \"capped honey cells\"", YELLOW,
         f"brood {naive_pct['brood']:.0f}% · honey {naive_pct['honey']:.0f}%"),
        ("HiveLens: SAM comb + bees, Muse Spark labels tiles", viz.GREEN,
         f"honey {f['honey']:.0f}% · brood {f['brood']:.0f}% · empty {f['empty']:.0f}%"),
    ]
    for x0, img, (label, color, big) in zip((40, 980), (left, right), texts):
        p, _ = _panel(img, pw, ph)
        c.paste(p, (x0, y0))
        d.rectangle((x0, y0, x0 + p.size[0], y0 + p.size[1]), outline=color, width=4)
        d.text((x0, y0 + p.size[1] + 16), label, fill=(40, 40, 40), font=viz._font(24))
        d.text((x0, y0 + p.size[1] + 52), big, fill=color, font=viz._font(46))
    lx = 980
    for key in ("honey", "brood", "larvae", "pollen", "empty"):
        d.rectangle((lx, 990, lx + 18, 1008), fill=viz.CLASS_COLORS[key], outline=(60, 60, 60))
        d.text((lx + 26, 988), viz.CLASS_LABELS[key], fill=(60, 60, 60), font=viz._font(18))
        lx += 36 + int(d.textlength(viz.CLASS_LABELS[key], font=viz._font(18)))
    d.text((40, 1030), "Percent of the comb outline. No comb benchmark yet: this shows behaviour, not accuracy.",
           fill=(70, 70, 70), font=viz._font(22))
    return c


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--board", default="IMG_5582")
    ap.add_argument("--days", type=float, default=3)
    ap.add_argument("--frames", type=int, default=99, help="how many photos from data/demo/comb/ (0 = skip comb)")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    numbers: dict = {"models": {"segmentation": config.SEGMENT_MODEL, "reasoning": config.REASONING_MODEL}}

    path = next(p for p in (config.DATA_DIR / "varroa").rglob(args.board + ".*") if p.suffix.lower() in (".jpg", ".jpeg"))
    board = Image.open(path).convert("RGB")  # loaded exactly like seed_demo/eval, so SAM answers come from cache
    expert = expert_boxes(args.board)
    print(f"board {args.board}: expert {len(expert)} mites")

    print("naive SAM 3.1 on the whole photo…")
    naive = sam.segment(board, measure.MITE_CONCEPT)  # whole image, downscaled to 1600 px
    print(f"   {len(naive)} found")
    print("naive Muse Spark count…")
    muse_n, muse_raw = naive_muse_count(board)
    print(f"   {muse_n}")
    print("HiveLens pipeline…")
    hl = measure.measure_varroa(board, args.days, progress=lambda i, n: print(f"   SAM crop {i}/{n}", end="\r"))
    print(f"\n   {hl.count} counted, {len(hl.rejected)} rejected")

    board_comparison(board, args.board, naive, hl, expert, muse_n).save(OUT / f"{args.board}_naive_vs_hivelens.jpg", quality=92)
    viz.evidence_sheet(board, hl, title=f"{args.board}: every counted mite and the rejected candidates").save(
        OUT / f"{args.board}_evidence.jpg", quality=92)
    for k, s in enumerate(viz.muse_sheets(board, hl), 1):
        s.save(OUT / f"{args.board}_muse_sheet_{k}.jpg", quality=92)
    viz.varroa_overlay(board, hl).save(OUT / f"{args.board}_overlay.jpg", quality=90)

    reasons: dict[str, int] = {}
    for _, why in hl.rejected:
        key = re.sub(r"\s*\(.*\)|\s[\d.]+$", "", why)
        reasons[key] = reasons.get(key, 0) + 1
    numbers["board"] = {
        "name": args.board, "expert_mites": len(expert),
        "naive_sam_found": len(naive),
        "naive_muse_count": muse_n, "naive_muse_raw": muse_raw[:500],
        "hivelens_counted": hl.count,
        "hivelens_from_sam": sum(1 for i in hl.kept if "Muse" not in i.concept),
        "hivelens_from_muse_vote": sum(1 for i in hl.kept if "Muse" in i.concept),
        "spots_shown_to_muse": len(hl.vote_centers), "muse_said_mite": len(hl.vote_yes),
        "rejected": len(hl.rejected), "rejected_by_reason": reasons,
    }

    frames = sorted(p for p in (config.DATA_DIR / "demo" / "comb").glob("*")
                    if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"))[: args.frames]
    numbers["frames"] = []
    for fp in frames:
        frame = ImageOps.exif_transpose(Image.open(fp)).convert("RGB")
        print(f"frame {fp.name}: naive SAM + HiveLens…")
        res = measure.measure_comb(frame)
        scale, shape = measure._canvas(frame.size)
        _, comb = measure.comb_grid(frame.size, res.instances.get("comb", []))
        maps, pct = {}, {}
        for k, concept in NAIVE_COMB.items():
            found = sam.segment(frame, concept, max_side=1600, min_confidence=0.3)
            maps[k] = measure._rasterize(found, scale, shape) & comb
            pct[k] = 100.0 * maps[k].sum() / max(1, comb.sum())
        comb_comparison(frame, fp.stem, pct, maps, res).save(OUT / f"{fp.stem}_naive_vs_hivelens.jpg", quality=92)
        numbers["frames"].append({"name": fp.name, "naive_sam_pct_of_comb": {k: round(v, 1) for k, v in pct.items()},
                                  "hivelens_pct": {k: round(v, 1) for k, v in res.fractions.items()},
                                  "bees_counted": res.bee_count})
        print(f"   naive {pct} · hivelens {res.metrics()}")

    (OUT / "numbers.json").write_text(json.dumps(numbers, indent=2))
    print(f"\nDone → {OUT}")


if __name__ == "__main__":
    main()
