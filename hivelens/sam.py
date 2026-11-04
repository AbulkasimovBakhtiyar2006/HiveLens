"""SAM 3.1 segmentation through the Meta Model API.

* Sends an image + a text concept ("varroa mite", "capped honey cells", ...).
* Parses the streamed record grammar with Meta's own `meta-sam-parser`.
* Large photos (sticky boards are 8064x6048) are cut into overlapping tiles,
  because a mite is only ~30 px wide there; detections are merged back with NMS.
* Every API answer is cached on disk by (model, concept, image bytes), so
  re-running a demo or an evaluation does not spend credits twice.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import numpy as np
from PIL import Image

from . import config
from .meta_client import client, data_url, jpeg_bytes, resize_max_side


@dataclass
class Instance:
    concept: str
    box: tuple[float, float, float, float]  # x1, y1, x2, y2 in full-image pixels (half-open)
    confidence: float | None
    mask: np.ndarray | None = field(default=None, repr=False)  # bool, box-local, box-sized

    @property
    def width(self) -> float:
        return self.box[2] - self.box[0]

    @property
    def height(self) -> float:
        return self.box[3] - self.box[1]

    @property
    def area_px(self) -> float:
        if self.mask is not None and self.mask.size:
            return float(self.mask.sum())
        return self.width * self.height

    @property
    def center(self) -> tuple[float, float]:
        return ((self.box[0] + self.box[2]) / 2, (self.box[1] + self.box[3]) / 2)

    def to_json(self) -> dict:
        return {
            "concept": self.concept,
            "box": [round(v, 1) for v in self.box],
            "confidence": self.confidence,
            "area_px": round(self.area_px, 1),
        }


# ── API call + cache ──────────────────────────────────────────────────────────

def _cache_path(concept: str, payload: bytes) -> Path:
    key = hashlib.sha256(
        config.SEGMENT_MODEL.encode() + b"\0" + concept.encode() + b"\0" + payload
    ).hexdigest()
    return config.CACHE_DIR / "sam" / f"{key}.json"


def _call_sam(image: Image.Image, concept: str) -> str:
    """Returns the raw segmentation text the API streamed back."""
    stream = client().responses.create(
        model=config.SEGMENT_MODEL,
        input=[
            {
                "type": "message",
                "role": "user",
                "content": [
                    {"type": "input_text", "text": concept},
                    {"type": "input_image", "image_url": data_url(image, quality=92)},
                ],
            }
        ],
        metadata={"include_confidence": "true", "mask_encoding": "one_bit"},
        stream=True,
    )
    parts: list[str] = []
    for event in stream:
        etype = getattr(event, "type", "")
        if etype == "response.output_text.delta":
            parts.append(event.delta)
        elif etype in ("response.failed", "error"):
            raise RuntimeError(f"SAM request failed: {event}")
    return "".join(parts)


def raw_segment(image: Image.Image, concept: str, use_cache: bool = True) -> str:
    payload = jpeg_bytes(image, 92)
    path = _cache_path(concept, payload)
    if use_cache and path.exists():
        return json.loads(path.read_text())["raw"]
    raw = _call_sam(image, concept)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"concept": concept, "size": image.size, "raw": raw}))
    return raw


# ── parsing ───────────────────────────────────────────────────────────────────

def parse_raw(raw: str, concept: str, offset: tuple[float, float] = (0, 0), scale: float = 1.0) -> list[Instance]:
    """Turns the API text into Instances. `scale` maps sent-image px to original px."""
    from meta_sam_parser import CompletedOutcome, decode_mask_to_raster, image_segmentation_format

    if not raw.strip():
        return []
    parser = image_segmentation_format().create_parser()
    parser.push(raw if raw.endswith("\n") else raw + "\n")
    result = parser.finish(CompletedOutcome()).result

    boxes: dict[str, object] = {}
    masks: dict[str, object] = {}
    for rec in result.records:
        if rec.kind == "box":
            boxes[rec.object_id] = rec
        elif rec.kind == "mask":
            masks[rec.object_id] = rec

    ox, oy = offset
    out: list[Instance] = []
    for oid, b in boxes.items():
        x1, y1, x2, y2 = b.left, b.top, b.right, b.bottom
        mask = None
        m = masks.get(oid)
        if m is not None:
            raster = np.frombuffer(decode_mask_to_raster(m.mask), dtype=np.uint8)
            raster = raster.reshape(m.mask.height, m.mask.width).astype(bool)
            bw = max(1, round((x2 - x1) * scale))
            bh = max(1, round((y2 - y1) * scale))
            if raster.shape != (bh, bw):
                import cv2

                raster = cv2.resize(raster.astype(np.uint8), (bw, bh), interpolation=cv2.INTER_NEAREST).astype(bool)
            mask = raster
        out.append(
            Instance(
                concept=concept,
                box=(ox + x1 * scale, oy + y1 * scale, ox + x2 * scale, oy + y2 * scale),
                confidence=b.confidence,
                mask=mask,
            )
        )
    return out


# ── public entry point ────────────────────────────────────────────────────────

def _iou(a, b) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    if inter <= 0:
        return 0.0
    ua = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / ua if ua > 0 else 0.0


def nms(instances: list[Instance], iou: float = 0.5) -> list[Instance]:
    ranked = sorted(instances, key=lambda i: -(i.confidence if i.confidence is not None else 0.5))
    kept: list[Instance] = []
    for inst in ranked:
        if all(_iou(inst.box, k.box) < iou for k in kept):
            kept.append(inst)
    return kept


def _starts(length: int, tile: int, overlap: int) -> list[int]:
    """Evenly spaced tile starts; the last tile ends exactly at the border (no thin slivers)."""
    if length <= tile:
        return [0]
    n = math.ceil((length - overlap / 2) / (tile - overlap / 2))
    n = max(n, 2)
    return [round(i * (length - tile) / (n - 1)) for i in range(n)]


def tiles(w: int, h: int, tile: int, overlap: int):
    for y in _starts(h, tile, overlap):
        for x in _starts(w, tile, overlap):
            yield x, y, min(x + tile, w), min(y + tile, h)


def segment_crops(
    image: Image.Image,
    concept: str,
    windows: list[tuple[int, int, int, int]],
    *,
    use_cache: bool = True,
    workers: int = 8,
    progress: Callable[[int, int], None] | None = None,
) -> list[Instance]:
    """Runs SAM on many crops of one image in parallel; results are in image coordinates.

    Progress is reported from the calling thread, so it is safe to drive a UI with it.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    def one(win):
        x1, y1, x2, y2 = win
        crop = image.crop(win)
        return parse_raw(raw_segment(crop, concept, use_cache), concept, offset=(x1, y1))

    found: list[Instance] = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = [pool.submit(one, w) for w in windows]
        for i, fut in enumerate(as_completed(futures), 1):
            found += fut.result()
            if progress:
                progress(i, len(windows))
    return found


def segment(
    image: Image.Image,
    concept: str,
    *,
    max_side: int | None = 1600,
    tile: int | None = None,
    overlap: int = 64,
    min_confidence: float = 0.0,
    use_cache: bool = True,
    workers: int = 8,
    progress: Callable[[int, int], None] | None = None,
) -> list[Instance]:
    """Segments `concept` in `image`. Coordinates are always in the original image.

    tile=None  → the whole image is sent, downscaled to `max_side`.
    tile=N     → the image is cut into N×N crops at full resolution (small objects).
                 SAM resizes every input internally, so a smaller tile makes a small
                 object look bigger to the model.
    """
    image = image.convert("RGB")
    w, h = image.size

    if not tile:
        small = resize_max_side(image, max_side)
        scale = w / small.size[0]
        found = parse_raw(raw_segment(small, concept, use_cache), concept, scale=scale)
        if progress:
            progress(1, 1)
    else:
        found = segment_crops(image, concept, list(tiles(w, h, tile, overlap)),
                              use_cache=use_cache, workers=workers, progress=progress)
        found = nms(found, 0.4)

    return [i for i in found if i.confidence is None or i.confidence >= min_confidence]
