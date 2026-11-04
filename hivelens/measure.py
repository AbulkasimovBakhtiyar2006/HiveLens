"""Deterministic measurement engine.

SAM 3.1 finds objects; this module turns them into numbers with plain code
(pixel areas, counts, size statistics). No model runs here, so every number
the agent is allowed to state can be traced back to a mask.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np
from PIL import Image

from . import sam
from .config import THRESHOLDS
from .sam import Instance

# ── Varroa: sticky board ──────────────────────────────────────────────────────

MITE_CONCEPT = "varroa mite"


@dataclass
class VarroaResult:
    count: int
    days_on_board: float
    mites_per_day: float
    kept: list[Instance] = field(default_factory=list)
    rejected: list[tuple[Instance, str]] = field(default_factory=list)
    median_area_px: float = 0.0
    # what Muse Spark was shown (spot centres, in contact-sheet order) and the indices it voted "mite"
    vote_centers: list[tuple[float, float]] = field(default_factory=list)
    vote_yes: list[int] = field(default_factory=list)

    def metrics(self) -> dict:
        return {
            "mite_count": self.count,
            "days_on_board": self.days_on_board,
            "mites_per_day": round(self.mites_per_day, 2),
            "rejected_detections": len(self.rejected),
        }


# Physical plausibility of a candidate, measured on the photo itself.
# A varroa mite is a smooth, flat, reddish-brown oval; wax crumbs are irregular,
# insect fragments are elongated rods. Thresholds were set on development boards
# (104 detections with expert labels) and are reported on separate held-out boards.
# Areas are fractions of width² because boards are photographed at different distances.
MITE_AREA_FRAC = (2.8e-5, 6.0e-5)   # dark body ≈ 1000-2200 px² on a 6048 px wide photo
MITE_MIN_REDNESS = 10               # (R-G) of the body minus (R-G) of the board around it
MITE_MAX_ASPECT = 1.8               # long / short axis of the fitted ellipse
MITE_MIN_FILL = 0.90                # body area / fitted ellipse area (crumbs are ragged)


def mite_body(board_arr: np.ndarray, center: tuple[float, float]) -> dict | None:
    """Finds the dark body under a detection and measures its size and redness."""
    H, W = board_arr.shape[:2]
    r = max(20, int(0.0083 * W))
    cx, cy = int(center[0]), int(center[1])
    x0, y0, x1, y1 = max(0, cx - r), max(0, cy - r), min(W, cx + r), min(H, cy + r)
    a = board_arr[y0:y1, x0:x1].astype(np.float32)
    if a.size == 0:
        return None
    v = a.max(axis=2)
    dark = v < np.median(v) - 60
    if not dark.any() or dark.all():
        return None
    n, labels, stats, _ = cv2.connectedComponentsWithStats(dark.astype(np.uint8), 8)
    ly, lx = cy - y0, cx - x0
    core = labels[max(0, ly - 5): ly + 6, max(0, lx - 5): lx + 6]
    ids = [i for i in np.unique(core) if i]
    k = max(ids, key=lambda i: stats[i, 4]) if ids else 1 + int(np.argmax(stats[1:, 4]))
    mask = labels == k
    body = a[mask]
    bg = np.median(a[~dark], axis=0)
    redness = float((body[:, 0] - body[:, 1]).mean() - (bg[0] - bg[1]))
    aspect, fill, ellipse = 9.0, 0.0, None
    cnts, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if cnts:
        cnt = max(cnts, key=cv2.contourArea)
        if len(cnt) >= 5:
            (ex, ey), (ax1, ax2), ang = cv2.fitEllipse(cnt)
            aspect = max(ax1, ax2) / max(1e-3, min(ax1, ax2))
            fill = cv2.contourArea(cnt) / (np.pi * ax1 * ax2 / 4 + 1e-6)
            ellipse = ((float(ex + x0), float(ey + y0)), (float(ax1), float(ax2)), float(ang))  # board px
    return {"area_frac": float(stats[k, 4]) / (W * W), "redness": redness, "aspect": aspect, "fill": fill,
            "ellipse": ellipse}


def filter_mites(
    instances: list[Instance], board: Image.Image | None = None, min_conf: float = 0.35
) -> tuple[list[Instance], list[tuple[Instance, str]]]:
    """Physical sanity checks on SAM detections.

    With the photo: every detection must sit on a dark body of mite size that is
    reddish-brown relative to the board and shaped like a smooth oval. Without the photo: size consistency between detections.
    """
    rejected: list[tuple[Instance, str]] = []
    pool: list[Instance] = []
    for inst in instances:
        if inst.confidence is not None and inst.confidence < min_conf:
            rejected.append((inst, f"low confidence {inst.confidence:.2f}"))
            continue
        w, h = max(inst.width, 1), max(inst.height, 1)
        aspect = max(w, h) / min(w, h)
        if aspect > 3.0:
            rejected.append((inst, f"too elongated (aspect {aspect:.1f})"))
            continue
        pool.append(inst)

    if board is not None:
        arr = np.asarray(board.convert("RGB"))
        lo, hi = MITE_AREA_FRAC
        kept = []
        for inst in pool:
            b = mite_body(arr, inst.center)
            if b is None:
                rejected.append((inst, "no dark body under the detection"))
            elif b["area_frac"] < lo:
                rejected.append((inst, "too small for a mite"))
            elif b["area_frac"] > hi:
                rejected.append((inst, "too large for a mite"))
            elif b["redness"] < MITE_MIN_REDNESS:
                rejected.append((inst, f"not reddish-brown (redness {b['redness']:.0f})"))
            elif b["aspect"] > MITE_MAX_ASPECT:
                rejected.append((inst, f"too elongated for a mite (aspect {b['aspect']:.1f})"))
            elif b["fill"] < MITE_MIN_FILL:
                rejected.append((inst, f"ragged outline, not an oval (fill {b['fill']:.2f})"))
            else:
                kept.append(inst)
        return kept, rejected

    if len(pool) >= 5:
        med = float(np.median([i.area_px for i in pool]))
        kept = []
        for inst in pool:
            r = inst.area_px / med if med else 1
            if r > 4:
                rejected.append((inst, f"{r:.1f}x larger than a typical mite"))
            elif r < 0.25:
                rejected.append((inst, f"{1 / r:.1f}x smaller than a typical mite"))
            else:
                kept.append(inst)
        return kept, rejected
    return pool, rejected


# SAM 3.1 finds mites reliably only when a mite fills enough of its input
# (probe on expert-annotated boards: 1344 px crops 0/3, 600 px 2/3, 300 px 3/3,
# all with zero false hits). So the board is read in two passes.
GRID_TILE = 600
REFINE_CROP = 300
MAX_REFINE = 250   # SAM 300 px re-checks per board
MAX_VOTE = 250     # spots shown to Muse Spark per board


def measure_varroa(
    board: Image.Image,
    days_on_board: float,
    *,
    tile: int = GRID_TILE,
    refine: bool = True,
    muse_vote: bool = True,
    progress=None,
) -> VarroaResult:
    """Pass 1: SAM 3.1 over a grid of `tile` px crops.
    Pass 2: every dark mite-sized blob that pass 1 did not explain is re-checked by
            SAM 3.1 on a tight 300 px crop, where a mite is large enough to be recognised.
    Pass 3: the dark spots SAM still did not recognise go to Muse Spark on numbered
            contact sheets; its votes become candidates.
    Every candidate from every pass then has to pass the physical checks."""
    board = board.convert("RGB")
    say = progress or (lambda i, n: None)
    n_grid = len(list(sam.tiles(*board.size, tile, 64)))
    found = sam.segment(board, MITE_CONCEPT, tile=tile, progress=lambda i, n: say(i, n_grid + (MAX_REFINE if refine else 0)))

    if refine:
        windows = refine_windows(board, found)
        extra = sam.segment_crops(board, MITE_CONCEPT, windows,
                                  progress=lambda i, n: say(n_grid + i, n_grid + n))
        found = sam.nms(found + extra, 0.3)

    centers: list[tuple[float, float]] = []
    voted: list[int] = []
    if muse_vote:
        from . import vote

        centers = unexplained_spots(board, found)[:MAX_VOTE]
        if centers:
            voted = vote.vote_mites(board, centers)
            r = max(12, int(0.0035 * board.size[0]))
            found += [Instance(MUSE_CONCEPT, (cx - r, cy - r, cx + r, cy + r), None)
                      for cx, cy in (centers[k] for k in voted)]

    kept, rejected = filter_mites(found, board)
    days = max(float(days_on_board or 1), 0.25)
    med = float(np.median([i.area_px for i in kept])) if kept else 0.0
    return VarroaResult(len(kept), days, len(kept) / days, kept, rejected, med, centers, voted)


MUSE_CONCEPT = "varroa mite (Muse Spark vote)"


def unexplained_spots(board: Image.Image, found: list[Instance]) -> list[tuple[float, float]]:
    """Centres of dark mite-sized blobs that no detection so far sits on, darkest first."""
    centers = [i.center for i in found]
    out = []
    for x1, y1, x2, y2 in classic_cv_mites(board):
        cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
        if not any(abs(cx - fx) < 60 and abs(cy - fy) < 60 for fx, fy in centers):
            out.append((cx, cy))
    return out


def refine_windows(board: Image.Image, found: list[Instance]) -> list[tuple[int, int, int, int]]:
    """300 px windows around candidate blobs that no SAM detection already covers."""
    w, h = board.size
    centers = [i.center for i in found]
    half = REFINE_CROP // 2
    wins: list[tuple[int, int, int, int]] = []
    taken: list[tuple[float, float]] = []
    for x1, y1, x2, y2 in classic_cv_mites(board):  # darkest first
        cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
        if any(abs(cx - fx) < 60 and abs(cy - fy) < 60 for fx, fy in centers):
            continue  # already found in pass 1
        if any(abs(cx - tx) < half * 0.6 and abs(cy - ty) < half * 0.6 for tx, ty in taken):
            continue  # an earlier window already covers this blob
        ox = int(min(max(cx - half, 0), max(w - REFINE_CROP, 0)))
        oy = int(min(max(cy - half, 0), max(h - REFINE_CROP, 0)))
        wins.append((ox, oy, min(ox + REFINE_CROP, w), min(oy + REFINE_CROP, h)))
        taken.append((cx, cy))
        if len(wins) >= MAX_REFINE:
            break
    return wins


def classic_cv_mites(board: Image.Image) -> list[tuple[float, float, float, float]]:
    """Mite-sized blobs much darker than the board. No model involved.

    Colour is unreliable (under the board lighting a mite's core reads grey-violet
    with low saturation), but darkness is not: mite cores sit at ~40-70 brightness
    on a ~220 board, while wax crumbs are clearly lighter. Used as the benchmark
    baseline and to propose spots for the 300 px SAM re-check, darkest first.
    """
    img = np.array(board.convert("RGB"))
    h, w = img.shape[:2]
    val = img.max(axis=2)  # HSV value
    bg = float(np.median(val))
    thr = min(90.0, 0.4 * bg)  # a softer threshold merges mites with nearby crumbs (tested: worse)
    mask = cv2.morphologyEx((val < thr).astype(np.uint8) * 255, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    # size is relative to the photo: boards are shot at different distances
    lo, hi = (0.0018 * w) ** 2, (0.012 * w) ** 2  # a mite body is ~25-35 px on a 6048 px wide photo
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    if n <= 1:
        return []
    mean_val = np.bincount(labels.ravel(), weights=val.ravel().astype(np.float64), minlength=n) / np.maximum(stats[:, 4], 1)
    out = []
    for i in range(1, n):
        x, y, bw, bh, area = stats[i]
        if lo <= area <= hi and max(bw, bh) / max(1, min(bw, bh)) <= 3:
            out.append((float(mean_val[i]), (float(x), float(y), float(x + bw), float(y + bh))))
    return [b for _, b in sorted(out)]


# ── Comb: frame photo ─────────────────────────────────────────────────────────

# SAM 3.1 outlines the comb and finds bees very well, but a "capped honey cells" prompt
# returns one region covering the whole frame (tested on three Commons frames: 85-93%
# "brood"). So SAM gives the geometry, and Muse Spark labels a grid of comb tiles.
COMB_SAM = {"comb": "honeycomb", "bees": "honey bee"}
TILE_CLASSES = {"H": "honey", "B": "brood", "L": "larvae", "P": "pollen", "N": "empty"}  # "X" = unreadable
GRID_COLS = 8
CANVAS_MAX = 1024


@dataclass
class CombResult:
    fractions: dict[str, float]  # percent of readable comb
    honey_kg_side: float
    class_maps: dict[str, np.ndarray] = field(repr=False, default_factory=dict)
    instances: dict[str, list[Instance]] = field(repr=False, default_factory=dict)
    canvas_scale: float = 1.0
    comb_from_mask: bool = True
    tile_labels: dict[int, str] = field(default_factory=dict)
    bee_count: int = 0

    def metrics(self) -> dict:
        m = {f"{k}_pct": round(v, 1) for k, v in self.fractions.items()}
        m["honey_kg_this_side"] = round(self.honey_kg_side, 2)
        m["bees_counted"] = self.bee_count
        m["tiles_read"] = sum(1 for v in self.tile_labels.values() if v in TILE_CLASSES)
        return m


def _rasterize(instances: list[Instance], scale: float, shape: tuple[int, int]) -> np.ndarray:
    canvas = np.zeros(shape, dtype=bool)
    H, W = shape
    for inst in instances:
        x1, y1, x2, y2 = (int(round(v * scale)) for v in inst.box)
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(W, max(x2, x1 + 1)), min(H, max(y2, y1 + 1))
        if x2 <= x1 or y2 <= y1:
            continue
        if inst.mask is None:
            canvas[y1:y2, x1:x2] = True
            continue
        m = cv2.resize(inst.mask.astype(np.uint8), (x2 - x1, y2 - y1), interpolation=cv2.INTER_NEAREST).astype(bool)
        canvas[y1:y2, x1:x2] |= m
    return canvas


def _canvas(size: tuple[int, int]) -> tuple[float, tuple[int, int]]:
    w, h = size
    scale = min(1.0, CANVAS_MAX / max(w, h))
    return scale, (max(1, round(h * scale)), max(1, round(w * scale)))


def comb_grid(size: tuple[int, int], comb_instances: list[Instance], cols: int = GRID_COLS):
    """Tiles over the comb's bounding box: [(x1, y1, x2, y2) in image px, comb coverage 0..1]."""
    scale, shape = _canvas(size)
    comb = _rasterize(comb_instances, scale, shape)
    if comb.mean() < 0.2:
        comb = np.ones(shape, bool)  # no usable outline: read the whole photo
    ys, xs = np.nonzero(comb)
    bx1, by1, bx2, by2 = xs.min(), ys.min(), xs.max() + 1, ys.max() + 1
    rows = max(3, round(cols * (by2 - by1) / max(1, bx2 - bx1)))
    out = []
    for r in range(rows):
        for c in range(cols):
            x1 = bx1 + (bx2 - bx1) * c // cols
            x2 = bx1 + (bx2 - bx1) * (c + 1) // cols
            y1 = by1 + (by2 - by1) * r // rows
            y2 = by1 + (by2 - by1) * (r + 1) // rows
            cover = float(comb[y1:y2, x1:x2].mean()) if x2 > x1 and y2 > y1 else 0.0
            out.append(((x1 / scale, y1 / scale, x2 / scale, y2 / scale), cover))
    return out, comb


def comb_from_tiles(size, found: dict[str, list[Instance]], tiles, labels: dict[int, str]) -> CombResult:
    """Per-pixel accounting: SAM bee masks first (they hide the comb), then each tile's label."""
    scale, shape = _canvas(size)
    _, comb = comb_grid(size, found.get("comb", []))
    bees = _rasterize(found.get("bees", []), scale, shape) & comb
    maps = {k: np.zeros(shape, bool) for k in list(TILE_CLASSES.values())}
    readable = bees.copy()
    for i, ((x1, y1, x2, y2), _) in enumerate(tiles):
        cls = TILE_CLASSES.get(labels.get(i, "X"))
        if not cls:
            continue
        sl = (slice(int(y1 * scale), int(y2 * scale)), slice(int(x1 * scale), int(x2 * scale)))
        region = np.zeros(shape, bool)
        region[sl] = True
        region &= comb
        maps[cls] |= region & ~bees
        readable |= region
    maps["bees"] = bees
    total = float(readable.sum()) or 1.0
    fractions = {k: 100.0 * float((m & readable).sum()) / total for k, m in maps.items()}
    honey_kg = fractions["honey"] / 100.0 * THRESHOLDS.honey_kg_full_frame / 2  # one side of the frame
    return CombResult(fractions, honey_kg, maps, found, scale, True, labels, len(found.get("bees", [])))


def measure_comb(frame: Image.Image, progress=None) -> CombResult:
    from concurrent.futures import ThreadPoolExecutor

    from . import vote

    frame = frame.convert("RGB")
    with ThreadPoolExecutor(max_workers=2) as pool:
        futs = {k: pool.submit(sam.segment, frame, c, max_side=1600, min_confidence=0.3) for k, c in COMB_SAM.items()}
        found = {k: f.result() for k, f in futs.items()}
    if progress:
        progress(1, 2)
    tiles, _ = comb_grid(frame.size, found["comb"])
    readable = [i for i, (_, cover) in enumerate(tiles) if cover >= 0.5]
    got = vote.label_tiles(frame, [tiles[i][0] for i in readable])
    labels = {readable[k]: v for k, v in got.items()}
    if progress:
        progress(2, 2)
    return comb_from_tiles(frame.size, found, tiles, labels)


def extra_concept(image: Image.Image, concept: str) -> dict:
    """Used by the agent's free-form `segment` tool (e.g. 'queen cell', 'drone brood')."""
    found = sam.segment(image, concept, max_side=1600, min_confidence=0.3)
    w, h = image.size
    area = sum(i.area_px for i in found)
    return {
        "concept": concept,
        "count": len(found),
        "area_pct_of_photo": round(100 * area / (w * h), 2),
        "mean_confidence": round(float(np.mean([i.confidence or 0 for i in found])), 3) if found else None,
    }
