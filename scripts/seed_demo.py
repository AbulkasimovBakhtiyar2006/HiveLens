"""Builds a demo hive with a few weekly inspections so the history and trend charts have data.

    python scripts/seed_demo.py --boards 3                # boards from the varroa dataset
    python scripts/seed_demo.py --boards 3 --no-agent     # cheaper: measurements only

Frame photos are optional: put your own comb photos (or openly licensed ones)
into data/demo/comb/ and they are used one per inspection.

The dataset boards come from different colonies; for the demo they are shown as
consecutive weekly inspections of one hive. The README says so explicitly.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

from PIL import Image, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from hivelens import config, store  # noqa: E402
from hivelens.pipeline import run_inspection  # noqa: E402

Image.MAX_IMAGE_PIXELS = None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--boards", type=int, default=3)
    ap.add_argument("--days", type=float, default=3)
    ap.add_argument("--no-agent", action="store_true")
    ap.add_argument("--name", default="Demo hive")
    ap.add_argument("--frames-in-hive", type=int, default=10)
    ap.add_argument("--pick", default="", help="comma-separated board names in inspection order, e.g. IMG_5651,IMG_5560,IMG_5582")
    args = ap.parse_args()

    root = config.DATA_DIR / "varroa"
    xml_stems = {p.stem for p in root.rglob("*.xml")}
    boards = sorted(p for p in root.rglob("*") if p.suffix.lower() in (".jpg", ".jpeg") and p.stem in xml_stems)
    combs = sorted(p for p in (config.DATA_DIR / "demo" / "comb").glob("*") if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"))
    if not boards and not combs:
        sys.exit("Nothing to seed. Run scripts/download_varroa.py or add photos to data/demo/comb/.")

    # pick boards with increasing mite load, so the demo shows a rising trend
    def n_mites(p: Path) -> int:
        xml = next(root.rglob(p.stem + ".xml"))
        return xml.read_text().count("<object>")

    if args.pick:
        by_stem = {p.stem: p for p in boards}
        picked = [by_stem[n.strip()] for n in args.pick.split(",") if n.strip() in by_stem]
    else:
        picked = sorted(boards, key=n_mites)
        step = max(1, len(picked) // max(1, args.boards))
        picked = picked[::step][: args.boards]

    hive = store.create_hive(args.name, "demo apiary", store.ensure_farm("Home apiary")["id"])
    n = max(len(picked), min(len(combs), args.boards))
    start = date.today() - timedelta(weeks=n - 1)
    for k in range(n):
        board = Image.open(picked[k]).convert("RGB") if k < len(picked) else None
        frames = [ImageOps.exif_transpose(Image.open(combs[k % len(combs)])).convert("RGB")] if combs else []
        d = (start + timedelta(weeks=k)).isoformat()
        print(f"→ inspection {d}: board={picked[k].name if board else '-'} frames={len(frames)}")
        rec = run_inspection(hive["id"], d, frames=frames, board=board, days_on_board=args.days,
                             frames_in_hive=args.frames_in_hive,
                             sample_sources={"board_sample": picked[k].name if board else None,
                                             "frame_samples": [combs[k % len(combs)].name] if combs else [],
                                             "dates": "Synthetic weekly dates for demonstration; source photos are not a longitudinal colony study."},
                             use_agent=not args.no_agent, progress=lambda m, f: print(f"   {m}"))
        print(f"   status {rec['status']['overall']}, metrics {rec['metrics']}")
    print(f"Demo hive ready: {hive['id']}  →  streamlit run app.py")


if __name__ == "__main__":
    main()
