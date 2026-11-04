"""Explains every miss and false hit of the varroa pipeline on annotated boards.

Uses only cached SAM answers from a previous eval run (no API calls if the cache is warm).
Writes data/eval/debug/<image>.json and small crops of each miss / false hit.

    python scripts/debug_varroa.py --n 2
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from hivelens import config, measure, sam  # noqa: E402
from eval_varroa import expert_boxes, pick_images  # noqa: E402

Image.MAX_IMAGE_PIXELS = None


def near(c, box, pad=25):
    return box[0] - pad <= c[0] <= box[2] + pad and box[1] - pad <= c[1] <= box[3] + pad


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=2)
    args = ap.parse_args()
    out = config.DATA_DIR / "eval" / "debug"
    out.mkdir(parents=True, exist_ok=True)

    for img_path, xml_path in pick_images(config.DATA_DIR / "varroa", args.n, "validation"):
        board = Image.open(img_path).convert("RGB")
        gt = expert_boxes(xml_path)
        grid = sam.segment(board, measure.MITE_CONCEPT, tile=measure.GRID_TILE)
        wins = measure.refine_windows(board, grid)
        extra = sam.segment_crops(board, measure.MITE_CONCEPT, wins)
        merged = sam.nms(grid + extra, 0.3)
        kept, rejected = measure.filter_mites(merged, board)
        cands = measure.classic_cv_mites(board)

        report = {"image": img_path.stem, "experts": len(gt), "grid": len(grid), "windows": len(wins),
                  "extra": len(extra), "kept": len(kept), "rejected": len(rejected), "mites": [], "false_hits": []}
        for j, g in enumerate(gt):
            gc = ((g[0] + g[2]) / 2, (g[1] + g[3]) / 2)
            rank = next((r for r, b in enumerate(cands) if near(((b[0] + b[2]) / 2, (b[1] + b[3]) / 2), g)), None)
            rej = [why for i, why in rejected if near(i.center, g)]
            row = {
                "id": j, "box": [round(v) for v in g],
                "grid_hit": any(near(i.center, g) for i in grid),
                "cv_candidate_rank": rank,
                "window_covers": any(w[0] <= gc[0] <= w[2] and w[1] <= gc[1] <= w[3] for w in wins),
                "refine_hit": any(near(i.center, g) for i in extra),
                "kept": any(near(i.center, g) for i in kept),
                "rejected_reason": rej[0] if rej else None,
                "confidences": [round(i.confidence or 0, 3) for i in grid + extra if near(i.center, g)],
            }
            report["mites"].append(row)
            if not row["kept"]:
                cx, cy = gc
                board.crop((int(cx) - 100, int(cy) - 100, int(cx) + 100, int(cy) + 100)).save(out / f"{img_path.stem}_miss{j}.jpg", quality=90)
        for k, i in enumerate(kept):
            if not any(near(i.center, g) for g in gt):
                report["false_hits"].append({"center": [round(v) for v in i.center], "size": [round(i.width), round(i.height)],
                                             "conf": round(i.confidence or 0, 3), "from": "grid" if i in grid else "refine"})
                cx, cy = i.center
                board.crop((int(cx) - 100, int(cy) - 100, int(cx) + 100, int(cy) + 100)).save(out / f"{img_path.stem}_fp{k}.jpg", quality=90)
        report["kept_sizes"] = sorted([round(i.width), round(i.height)] for i in kept)
        report["rejected_all"] = [{"center": [round(v) for v in i.center], "size": [round(i.width), round(i.height)], "why": why}
                                  for i, why in rejected]
        (out / f"{img_path.stem}.json").write_text(json.dumps(report, indent=1))
        print(json.dumps({k: report[k] for k in ("image", "experts", "grid", "windows", "extra", "kept", "rejected")}))
        for m in report["mites"]:
            print("   ", m)
        print("    false hits:", len(report["false_hits"]))


if __name__ == "__main__":
    main()
