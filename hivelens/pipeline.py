"""One inspection end to end: SAM 3.1 → measurements → rules → Muse Spark agent → saved record."""

from __future__ import annotations

from datetime import datetime
from typing import Callable

from PIL import Image

from . import agent, config, engine, measure, store, viz


def run_inspection(
    hive_id: str,
    date: str,
    *,
    frames: list[Image.Image] | None = None,
    board: Image.Image | None = None,
    days_on_board: float = 3,
    frames_in_hive: int | None = None,
    note: str = "",
    use_agent: bool = True,
    board_tile: int = 600,
    board_refine: bool = True,
    progress: Callable[[str, float], None] | None = None,
    on_event: Callable[[dict], None] | None = None,
) -> dict:
    frames = frames or []
    if not frames and board is None:
        raise ValueError("Add at least one frame photo or a sticky board photo.")
    say = progress or (lambda msg, frac: None)

    photos: dict[str, Image.Image] = {}
    overlays: dict[str, Image.Image] = {}
    extras: dict[str, Image.Image] = {}  # evidence images (saved as <name>.jpg, listed in record["files"])
    detections: dict[str, list] = {}

    varroa_metrics = None
    if board is not None:
        say("SAM 3.1: looking for varroa mites on the sticky board", 0.05)
        res = measure.measure_varroa(
            board, days_on_board, tile=board_tile, refine=board_refine,
            progress=lambda i, n: say(f"SAM 3.1: board crop {i}/{n}", 0.05 + 0.4 * i / n),
        )
        varroa_metrics = res.metrics()
        photos["board"] = board
        overlays["board"] = viz.varroa_overlay(board, res)
        extras["board_evidence"] = viz.evidence_sheet(board, res, title=f"Sticky board {date}: what was counted and why")
        for k, sheet in enumerate(viz.muse_sheets(board, res), 1):
            extras[f"board_muse_sheet_{k}"] = sheet
        detections["board"] = {
            "kept": [i.to_json() for i in res.kept],
            "rejected": [{**i.to_json(), "reason": why} for i, why in res.rejected],
        }

    comb_metrics = []
    for n, frame in enumerate(frames, 1):
        pid = f"frame_{n}"
        say(f"SAM 3.1: reading comb on {pid}", 0.45 + 0.3 * (n - 1) / max(1, len(frames)))
        res = measure.measure_comb(frame)
        comb_metrics.append(res.metrics())
        photos[pid] = frame
        overlays[pid] = viz.comb_overlay(frame, res)
        detections[pid] = {k: len(v) for k, v in res.instances.items()}

    history = store.history_before(hive_id, date)
    previous = history[-1]["metrics"] if history else None
    metrics = engine.add_trends(engine.aggregate(varroa_metrics, comb_metrics, frames_in_hive), previous)
    status = engine.assess(metrics)

    record = {
        "date": date,
        "created": datetime.now().isoformat(timespec="seconds"),
        "models": {"segmentation": config.SEGMENT_MODEL, "reasoning": config.REASONING_MODEL},
        "inputs": {"days_on_board": days_on_board if board is not None else None,
                   "frames_in_hive": frames_in_hive, "note": note},
        "metrics": metrics,
        "per_photo": {"board": varroa_metrics, **{f"frame_{i}": m for i, m in enumerate(comb_metrics, 1)}},
        "detections": detections,
        "status": status,
    }

    if use_agent:
        say("Muse Spark: forming hypotheses and checking them", 0.8)
        run = agent.run_agent(photos, metrics, history, note=note, on_event=on_event)
        record.update(run.to_json())

    say("Saving inspection", 0.97)
    return store.save_inspection(hive_id, record, photos, overlays, extras)
