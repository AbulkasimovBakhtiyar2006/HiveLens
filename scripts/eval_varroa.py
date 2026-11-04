"""Benchmark: SAM 3.1 mite counts vs expert annotations vs a classic colour-threshold baseline.

    python scripts/eval_varroa.py --n 5            # 5 validation boards, uses the Meta API
    python scripts/eval_varroa.py --n 5 --dry-run  # no API: only experts vs classic CV

Writes data/eval/varroa_eval.json (shown in the Benchmark tab) and overlay images.
SAM answers are cached, so re-running costs nothing.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from hivelens import config, measure, sam  # noqa: E402

Image.MAX_IMAGE_PIXELS = None


def expert_boxes(xml_path: Path) -> list[tuple[float, float, float, float]]:
    root = ET.parse(xml_path).getroot()
    out = []
    for obj in root.iter("object"):
        bb = obj.find("bndbox")
        if bb is None:
            continue
        out.append(tuple(float(bb.find(k).text) for k in ("xmin", "ymin", "xmax", "ymax")))
    return out


def pick_images(root: Path, n: int, split: str) -> list[tuple[Path, Path]]:
    xml_by_stem = {p.stem: p for p in root.rglob("*.xml")}
    imgs = sorted(p for p in root.rglob("*") if p.suffix.lower() in (".jpg", ".jpeg", ".png") and p.stem in xml_by_stem)
    csv_path = root / "df_dataset.csv"
    if split != "all" and csv_path.exists():
        rows = list(csv.DictReader(csv_path.open()))
        col = next((c for c in (rows[0] if rows else {}) if any(str(r[c]).lower() in ("val", "validation", "test") for r in rows)), None)
        if col:
            wanted = {Path(str(r.get("file_images") or r.get("file_image") or next(iter(r.values())))).stem
                      for r in rows if str(r[col]).lower().startswith(split[:3])}
            name_cols = [c for c in rows[0] if "name" in c.lower() or "image" in c.lower()]
            for c in name_cols:
                wanted |= {Path(str(r[c])).stem for r in rows if str(r[col]).lower().startswith(split[:3])}
            sel = [p for p in imgs if p.stem in wanted]
            if sel:
                imgs = sel
    return [(p, xml_by_stem[p.stem]) for p in imgs[:n]]


def match(pred, gt, grow: float = 0.5):
    """Greedy match: a prediction counts if its centre falls inside a (slightly grown) expert box."""
    used = set()
    tp = 0
    for p in pred:
        cx, cy = (p[0] + p[2]) / 2, (p[1] + p[3]) / 2
        for j, g in enumerate(gt):
            if j in used:
                continue
            gw, gh = (g[2] - g[0]) * grow, (g[3] - g[1]) * grow
            if g[0] - gw <= cx <= g[2] + gw and g[1] - gh <= cy <= g[3] + gh:
                used.add(j)
                tp += 1
                break
    fp, fn = len(pred) - tp, len(gt) - tp
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "precision": round(prec, 3), "recall": round(rec, 3), "f1": round(f1, 3)}


def overlay(img: Image.Image, gt, pred, path: Path):
    a = np.array(img)
    s = 2000 / max(a.shape[:2])
    a = cv2.resize(a, (round(a.shape[1] * s), round(a.shape[0] * s)), interpolation=cv2.INTER_AREA)
    for g in gt:
        cv2.rectangle(a, (int(g[0] * s), int(g[1] * s)), (int(g[2] * s), int(g[3] * s)), (40, 120, 255), 2)
    for p in pred:
        cx, cy = int((p[0] + p[2]) / 2 * s), int((p[1] + p[3]) / 2 * s)
        cv2.circle(a, (cx, cy), 9, (30, 200, 60), 2)
    Image.fromarray(a).save(path, quality=88)


def _hits(center, gt, grow=0.5):
    cx, cy = center
    for j, g in enumerate(gt):
        gw, gh = (g[2] - g[0]) * grow, (g[3] - g[1]) * grow
        if g[0] - gw <= cx <= g[2] + gw and g[1] - gh <= cy <= g[3] + gh:
            return j
    return None


def detail_record(name, img, gt, kept, rejected, out):
    """Every kept and rejected candidate with its source and whether experts agree, plus cut-outs."""
    crops = out / "details"
    crops.mkdir(exist_ok=True)

    def cut(c, tag):
        x, y = int(c[0]), int(c[1])
        path = crops / f"{name}_{tag}_{x}_{y}.jpg"
        img.crop((x - 60, y - 60, x + 60, y + 60)).save(path, quality=88)
        return path.name

    rec = {"image": name, "kept": [], "rejected": [], "missed": []}
    matched = set()
    for i in kept:
        j = _hits(i.center, gt)
        tp = j is not None and j not in matched
        if tp:
            matched.add(j)
        rec["kept"].append({"center": [round(v) for v in i.center], "source": "muse" if "Muse" in i.concept else "sam",
                            "conf": None if i.confidence is None else round(i.confidence, 3), "tp": tp,
                            "crop": cut(i.center, "TP" if tp else "FP")})
    for i, why in rejected:
        j = _hits(i.center, gt)
        rec["rejected"].append({"center": [round(v) for v in i.center], "source": "muse" if "Muse" in i.concept else "sam",
                                "why": why, "was_mite": j is not None,
                                "crop": cut(i.center, "REJmite") if j is not None else None})
    for j, g in enumerate(gt):
        if j not in matched:
            c = ((g[0] + g[2]) / 2, (g[1] + g[3]) / 2)
            rec["missed"].append({"center": [round(v) for v in c], "crop": cut(c, "MISS")})
    return rec


def evaluate(n: int = 12, skip: int = 8, split: str = "validation", tile: int = measure.GRID_TILE,
             refine: bool = True, muse: bool = True, dry_run: bool = False,
             log=print, progress=None) -> dict:
    """Runs the benchmark and writes data/eval/varroa_eval.json. Also called from the app."""
    root = config.DATA_DIR / "varroa"
    pairs = pick_images(root, n + skip, split)[skip:]
    if not pairs:
        raise SystemExit("No images found. Run: python scripts/download_varroa.py")
    out = config.DATA_DIR / "eval"
    out.mkdir(parents=True, exist_ok=True)

    rows, sam_m, cv_m, details = [], [], [], []
    for k, (img_path, xml_path) in enumerate(pairs, 1):
        img = Image.open(img_path).convert("RGB")
        gt = expert_boxes(xml_path)
        n_tiles = len(list(sam.tiles(*img.size, tile, 64)))
        log(f"[{k}/{len(pairs)}] {img_path.stem} {img.size[0]}x{img.size[1]}: {len(gt)} expert mites"
            + ("" if dry_run else f", {n_tiles} grid crops + re-check of dark spots…"))
        cv_boxes = measure.classic_cv_mites(img)
        row = {"image": img_path.stem, "experts": len(gt), "classic_cv": len(cv_boxes)}
        cv_m.append(match(cv_boxes, gt))
        if not dry_run:
            res = measure.measure_varroa(
                img, 1, tile=tile, refine=refine, muse_vote=muse,
                progress=(lambda i, m, k=k: progress(k - 1 + i / m, len(pairs))) if progress else None)
            kept, rejected = res.kept, res.rejected
            sam_boxes = [i.box for i in kept]
            row.update({"sam": len(sam_boxes), "sam_rejected": len(rejected),
                        "muse_votes_kept": sum(1 for i in kept if "Muse" in i.concept)})
            m = match(sam_boxes, gt)
            sam_m.append(m)
            row.update({f"sam_{key}": v for key, v in m.items() if key in ("precision", "recall", "f1")})
            overlay(img, gt, sam_boxes, out / f"{img_path.stem}_sam.jpg")
            details.append(detail_record(img_path.stem, img, gt, kept, rejected, out))
        else:
            row["sam"] = None
        log(f"{img_path.stem}: experts {row['experts']}, HiveLens {row['sam']}, classic CV {row['classic_cv']}")
        rows.append(row)
        if progress:
            progress(k, len(pairs))

    def mae(key):
        vals = [abs(r[key] - r["experts"]) for r in rows if r.get(key) is not None]
        return round(float(np.mean(vals)), 2) if vals else None

    def pooled(ms, key):
        if not ms:
            return None
        tp, fp, fn = (sum(m[k] for m in ms) for k in ("tp", "fp", "fn"))
        p = tp / (tp + fp) if tp + fp else 0
        r = tp / (tp + fn) if tp + fn else 0
        f1 = 2 * p * r / (p + r) if p + r else 0.0
        return round({"precision": p, "recall": r, "f1": f1}[key], 3)

    summary = {"images": len(rows), "experts_total": sum(r["experts"] for r in rows),
               "sam_mae": mae("sam"), "cv_mae": mae("classic_cv"),
               "sam_precision": pooled(sam_m, "precision"), "sam_recall": pooled(sam_m, "recall"),
               "sam_f1": pooled(sam_m, "f1"), "cv_f1": pooled(cv_m, "f1"),
               "tile": tile, "refine": refine, "muse_vote": muse, "skipped_first": skip,
               "models": [config.SEGMENT_MODEL] + ([config.REASONING_MODEL] if muse else [])}
    result = {
        "summary": summary,
        "images": rows,
        "note": "Ground truth: expert boxes from Divasón et al. 2023 (Zenodo 10.5281/zenodo.10231845, CC BY 4.0). "
                "Zero-shot: SAM 3.1 with the prompt 'varroa mite' and Muse Spark votes on unexplained dark spots; "
                f"no training on this dataset. The first {skip} boards were used for development and are excluded.",
    }
    (out / "varroa_eval.json").write_text(json.dumps(result, indent=2))
    if details:
        (out / "varroa_details.json").write_text(json.dumps(details, indent=1))
    log(json.dumps(summary, indent=2))
    return result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=12)
    ap.add_argument("--skip", type=int, default=8, help="skip the first K boards (development boards used for tuning)")
    ap.add_argument("--split", default="validation", help="validation | train | all")
    ap.add_argument("--tile", type=int, default=measure.GRID_TILE)
    ap.add_argument("--no-refine", action="store_true", help="skip the 300 px re-check pass")
    ap.add_argument("--no-muse", action="store_true", help="skip the Muse Spark vote on unexplained spots")
    ap.add_argument("--dry-run", action="store_true", help="skip SAM (no API calls)")
    args = ap.parse_args()
    evaluate(args.n, args.skip, args.split, args.tile, not args.no_refine, not args.no_muse, args.dry_run)


if __name__ == "__main__":
    main()
