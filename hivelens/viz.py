"""Overlays for the UI and the exported archive."""

from __future__ import annotations

import cv2
import numpy as np
from PIL import Image

from .measure import CombResult, VarroaResult

CLASS_COLORS = {
    "honey": (245, 190, 40),
    "brood": (170, 110, 60),
    "larvae": (250, 250, 250),
    "pollen": (255, 120, 0),
    "bees": (60, 60, 60),
    "empty": (90, 170, 230),
}
CLASS_LABELS = {
    "honey": "Capped honey",
    "brood": "Capped brood",
    "larvae": "Open brood",
    "pollen": "Pollen",
    "bees": "Bees (cover comb)",
    "empty": "Empty / nectar",
}


def _fit(img: np.ndarray, max_side: int) -> tuple[np.ndarray, float]:
    h, w = img.shape[:2]
    s = min(1.0, max_side / max(h, w))
    if s < 1:
        img = cv2.resize(img, (round(w * s), round(h * s)), interpolation=cv2.INTER_AREA)
    return img, s


def varroa_overlay(board: Image.Image, res: VarroaResult, max_side: int = 2000) -> Image.Image:
    img, s = _fit(np.array(board.convert("RGB")), max_side)
    r = max(6, int(0.012 * max(img.shape[:2])))
    for inst in res.kept:
        cx, cy = (int(v * s) for v in inst.center)
        color = (40, 120, 255) if "Muse" in inst.concept else (30, 200, 60)  # blue: found by the Muse Spark vote
        cv2.circle(img, (cx, cy), r, color, 3)
    for inst, _ in res.rejected:
        cx, cy = (int(v * s) for v in inst.center)
        cv2.drawMarker(img, (cx, cy), (230, 40, 40), cv2.MARKER_TILTED_CROSS, r, 2)
    return Image.fromarray(img)


GREEN, BLUE, RED, GREY = (30, 170, 70), (40, 110, 240), (215, 45, 45), (120, 120, 120)


def _font(size: int):
    from PIL import ImageFont

    for name in ("DejaVuSans.ttf", "/System/Library/Fonts/Supplemental/Arial.ttf",
                 "/System/Library/Fonts/Helvetica.ttc", "/Library/Fonts/Arial.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _fit_text(d, text: str, font, width: int) -> str:
    if d.textlength(text, font=font) <= width:
        return text
    while text and d.textlength(text + "…", font=font) > width:
        text = text[:-1]
    return text + "…"


def evidence_sheet(board: Image.Image, res: VarroaResult, *, cols: int = 8, tile: int = 224,
                   max_tiles: int = 48, min_rejected: int = 16, title: str = "") -> Image.Image:
    """Close-ups of every counted mite and of the rejected candidates, each with the fitted
    ellipse and the numbers the physical checks used. Nothing here is a new measurement:
    it redraws what measure.filter_mites decided."""
    from PIL import ImageDraw

    from .measure import MITE_MAX_ASPECT, MITE_MIN_FILL, MITE_MIN_REDNESS, mite_body

    board = board.convert("RGB")
    arr = np.asarray(board)
    W = board.size[0]
    half = max(16, int(0.009 * W))  # ~110 px window on a 6048 px wide photo
    kept = sorted(res.kept, key=lambda i: "Muse" in i.concept)
    rej = sorted(res.rejected, key=lambda r: r[1].startswith(("low confidence", "too elongated (")))
    n_rej = min(len(rej), max(min_rejected, max_tiles - len(kept)))
    items = [(i, "muse" if "Muse" in i.concept else "sam", "") for i in kept[: max_tiles - n_rej]]
    items += [(i, "rej", why) for i, why in rej[:n_rej]]

    head, foot, pad = 24, 44, 8
    ch, cw = head + tile + foot, tile
    rows = max(1, (len(items) + cols - 1) // cols)
    top = 92
    sheet = Image.new("RGB", (pad + cols * (cw + pad), top + rows * (ch + pad) + pad), (248, 247, 244))
    d = ImageDraw.Draw(sheet)
    f_title, f_small, f_mid = _font(26), _font(13), _font(15)
    d.text((pad + 4, 12), title or "HiveLens evidence sheet", fill=(20, 20, 20), font=f_title)
    summary = (f"{res.count} counted ({sum(1 for i in res.kept if 'Muse' not in i.concept)} SAM 3.1, "
               f"{sum(1 for i in res.kept if 'Muse' in i.concept)} Muse Spark vote) · {len(res.rejected)} rejected by "
               f"physical checks · shown: {len(items)}")
    d.text((pad + 4, 48), summary, fill=(60, 60, 60), font=f_mid)
    rule = (f"a mite must be a dark, reddish-brown (redness ≥ {MITE_MIN_REDNESS}), smooth (fill ≥ {MITE_MIN_FILL}) "
            f"oval (aspect ≤ {MITE_MAX_ASPECT}) of mite size")
    d.text((pad + 4, 68), rule, fill=(110, 110, 110), font=f_small)

    colors = {"sam": GREEN, "muse": BLUE, "rej": RED}
    labels = {"sam": "SAM 3.1", "muse": "Muse Spark vote", "rej": "rejected"}
    src = lambda i: "Muse vote" if "Muse" in i.concept else "SAM 3.1"  # noqa: E731
    for n, (inst, kind, why) in enumerate(items):
        cx, cy = inst.center
        x0, y0 = cx - half, cy - half
        crop = np.array(board.crop((int(x0), int(y0), int(x0) + 2 * half, int(y0) + 2 * half)).resize((tile, tile)))
        body = mite_body(arr, inst.center)
        s = tile / (2 * half)
        col = colors[kind]
        if body and body.get("ellipse"):
            (ex, ey), (a1, a2), ang = body["ellipse"]
            cv2.ellipse(crop, ((float((ex - int(x0)) * s), float((ey - int(y0)) * s)), (float(a1 * s), float(a2 * s)), ang),
                        col, 2)
        x = pad + (n % cols) * (cw + pad)
        y = top + (n // cols) * (ch + pad)
        d.rectangle((x, y, x + cw - 1, y + ch - 1), fill="white", outline=col, width=3)
        d.rectangle((x, y, x + cw - 1, y + head), fill=col)
        head_text = f"#{n + 1}  {labels[kind]}" + (f" ({src(inst)})" if kind == "rej" else "")
        d.text((x + 6, y + 4), _fit_text(d, head_text, f_mid, cw - 10), fill="white", font=f_mid)
        sheet.paste(Image.fromarray(crop), (x, y + head))
        if body:
            line1 = f"aspect {body['aspect']:.2f} · red {body['redness']:+.0f} · fill {body['fill']:.2f}"
        else:
            line1 = f"{src(inst)} hit" + (f", confidence {inst.confidence:.2f}" if inst.confidence is not None else "")
        line2 = "MITE: counted" if kind != "rej" else why
        d.text((x + 6, y + head + tile + 5), _fit_text(d, line1, f_small, cw - 10), fill=(50, 50, 50), font=f_small)
        d.text((x + 6, y + head + tile + 23), _fit_text(d, line2, f_small, cw - 10),
               fill=(GREEN if kind != "rej" else RED), font=f_small)
    return sheet


def muse_sheets(board: Image.Image, res: VarroaResult, scale: int = 2, max_sheets: int = 4) -> list[Image.Image]:
    """The exact contact sheets Muse Spark was shown (rebuilt with the same code), with its answer
    and the physical check drawn on top. Blue = Muse said mite and the checks agreed (counted);
    red = Muse said mite, the checks said no. Unmarked = Muse said no.
    Only sheets with at least one "mite" vote are drawn (sheets with a veto first in importance)."""
    from PIL import ImageDraw

    from . import vote

    if not res.vote_centers:
        return []
    yes = set(res.vote_yes)
    counted = {(round(i.center[0]), round(i.center[1])) for i in res.kept if "Muse" in i.concept}
    per = vote.COLS * vote.COLS
    out = []
    n_sheets = (len(res.vote_centers) + per - 1) // per
    for s_i, first in enumerate(range(0, len(res.vote_centers), per)):
        chunk = res.vote_centers[first: first + per]
        if len(out) >= max_sheets or not any(first + k in yes for k in range(len(chunk))):
            continue
        raw = vote._sheet(board.convert("RGB"), chunk, first + 1)
        big = raw.resize((raw.size[0] * scale, raw.size[1] * scale), Image.NEAREST)
        top = 70
        img = Image.new("RGB", (big.size[0], big.size[1] + top), (248, 247, 244))
        img.paste(big, (0, top))
        d = ImageDraw.Draw(img)
        t = vote.TILE * scale
        n_yes = sum(1 for k in range(len(chunk)) if first + k in yes)
        d.text((10, 8), f"What Muse Spark saw: sheet {s_i + 1}/{n_sheets} · {len(chunk)} dark spots SAM 3.1 did not explain",
               fill=(20, 20, 20), font=_font(20))
        d.text((10, 38), f"Muse said 'mite' on {n_yes} · blue = counted after physical checks · red = vetoed by the checks",
               fill=(80, 80, 80), font=_font(15))
        for k, c in enumerate(chunk):
            if first + k not in yes:
                continue
            ok = (round(c[0]), round(c[1])) in counted
            x, y = (k % vote.COLS) * t, top + (k // vote.COLS) * t
            d.rectangle((x + 2, y + 2, x + t - 3, y + t - 3), outline=BLUE if ok else RED, width=6)
            if not ok:
                d.line((x + 8, y + 8, x + t - 9, y + t - 9), fill=RED, width=4)
        out.append(img)
    return out


def comb_overlay(frame: Image.Image, res: CombResult, max_side: int = 1400, alpha: float = 0.45) -> Image.Image:
    base = np.array(frame.convert("RGB"))
    shape = next(iter(res.class_maps.values())).shape if res.class_maps else base.shape[:2]
    small = cv2.resize(base, (shape[1], shape[0]), interpolation=cv2.INTER_AREA)
    color = small.copy()
    for key, m in res.class_maps.items():
        if key in CLASS_COLORS and m.any():
            color[m] = CLASS_COLORS[key]
    out = cv2.addWeighted(small, 1 - alpha, color, alpha, 0)
    out, _ = _fit(out, max_side)
    return Image.fromarray(out)
