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
