"""Finds which SAM 3.1 text prompt and crop size detect varroa mites on real boards.

Takes crops centred on expert-annotated mites, tries several prompts and crop sizes,
and reports how often a detection lands on the mite and how many false hits it makes.

    python scripts/probe_prompts.py            # ~80 SAM calls, cached
"""

from __future__ import annotations

import glob
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from hivelens import config, sam  # noqa: E402
from eval_varroa import expert_boxes  # noqa: E402

Image.MAX_IMAGE_PIXELS = None

PROMPTS = ["varroa mite", "mite", "tick", "bug", "insect", "beetle", "dark brown oval", "small dark red oval", "seed"]
SIZES = [1344, 600, 300]  # crop side in original pixels; SAM resizes every input internally


def main() -> None:
    root = config.DATA_DIR / "varroa"
    samples = []
    for xml in sorted(glob.glob(str(root / "**" / "*.xml"), recursive=True))[:6]:
        img_path = next(Path(xml).parent.parent.rglob(Path(xml).stem + ".jpg"))
        boxes = expert_boxes(Path(xml))
        if boxes:
            samples.append((img_path, boxes[0], boxes))
        if len(samples) == 3:
            break

    print(f"{'prompt':22} " + " ".join(f"{s:>12}" for s in SIZES))
    for prompt in PROMPTS:
        cells = []
        for size in SIZES:
            hit = extra = 0
            for img_path, (x1, y1, x2, y2), all_boxes in samples:
                img = Image.open(img_path).convert("RGB")
                cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
                ox, oy = int(cx - size / 2), int(cy - size / 2)
                crop = img.crop((ox, oy, ox + size, oy + size))
                found = sam.segment(crop, prompt, max_side=None)
                for f in found:
                    fx, fy = f.center[0] + ox, f.center[1] + oy
                    on_mite = any(b[0] - 20 <= fx <= b[2] + 20 and b[1] - 20 <= fy <= b[3] + 20 for b in all_boxes)
                    hit += on_mite
                    extra += not on_mite
            cells.append(f"{hit}/{len(samples)} +{extra}fp")
        print(f"{prompt:22} " + " ".join(f"{c:>12}" for c in cells), flush=True)
    print("\nCells: mites found / mites present, +false detections. Send me this table.")


if __name__ == "__main__":
    main()
