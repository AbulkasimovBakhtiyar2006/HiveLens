"""Hive registry: every hive keeps its inspections on disk, so trends build up over time.

Layout:
  data/hives/<hive_id>/hive.json
  data/hives/<hive_id>/<inspection_id>/inspection.json  (+ photos, overlays)
"""

from __future__ import annotations

import csv
import io
import json
import re
import zipfile
from datetime import datetime
from pathlib import Path

from PIL import Image

from . import config


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40] or "hive"


def _hive_dir(hive_id: str) -> Path:
    return config.HIVES_DIR / hive_id


def list_hives() -> list[dict]:
    if not config.HIVES_DIR.exists():
        return []
    out = []
    for p in sorted(config.HIVES_DIR.glob("*/hive.json")):
        out.append(json.loads(p.read_text()))
    return out


def create_hive(name: str, location: str = "") -> dict:
    base = _slug(name)
    hive_id, n = base, 2
    while _hive_dir(hive_id).exists():
        hive_id, n = f"{base}-{n}", n + 1
    hive = {"id": hive_id, "name": name, "location": location, "created": datetime.now().isoformat(timespec="seconds")}
    _hive_dir(hive_id).mkdir(parents=True, exist_ok=True)
    (_hive_dir(hive_id) / "hive.json").write_text(json.dumps(hive, indent=2))
    return hive


def inspections(hive_id: str) -> list[dict]:
    items = [json.loads(p.read_text()) for p in _hive_dir(hive_id).glob("*/inspection.json")]
    return sorted(items, key=lambda i: (i.get("date", ""), i.get("id", "")))


def history_before(hive_id: str, date: str) -> list[dict]:
    """Compact history for the agent: date + metrics + overall level."""
    return [
        {"date": i["date"], "metrics": i.get("metrics", {}), "overall": i.get("status", {}).get("overall")}
        for i in inspections(hive_id)
        if i.get("date", "") < date
    ]


def save_inspection(hive_id: str, record: dict, photos: dict[str, Image.Image], overlays: dict[str, Image.Image],
                    extras: dict[str, Image.Image] | None = None) -> dict:
    insp_id = record.get("id") or f"{record['date']}-{datetime.now().strftime('%H%M%S')}"
    record["id"] = insp_id
    folder = _hive_dir(hive_id) / insp_id
    folder.mkdir(parents=True, exist_ok=True)
    files = {}
    for name, img in photos.items():
        path = folder / f"{name}.jpg"
        img.convert("RGB").save(path, quality=90)
        files[name] = path.name
    for name, img in overlays.items():
        path = folder / f"{name}_overlay.jpg"
        img.convert("RGB").save(path, quality=88)
        files[f"{name}_overlay"] = path.name
    for name, img in (extras or {}).items():
        path = folder / f"{name}.jpg"
        img.convert("RGB").save(path, quality=90)
        files[name] = path.name
    record["files"] = files
    (folder / "inspection.json").write_text(json.dumps(record, indent=2, default=str))
    return record


def file_path(hive_id: str, insp_id: str, name: str) -> Path:
    return _hive_dir(hive_id) / insp_id / name


def metrics_rows(hive_id: str) -> list[dict]:
    rows = []
    for i in inspections(hive_id):
        rows.append({"date": i["date"], "overall": i.get("status", {}).get("overall"), **i.get("metrics", {})})
    return rows


def export_zip(hive_id: str) -> bytes:
    """Everything about one hive: metadata, a metrics CSV, every inspection with photos and reports."""
    buf = io.BytesIO()
    folder = _hive_dir(hive_id)
    rows = metrics_rows(hive_id)
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for path in folder.rglob("*"):
            if path.is_file():
                z.write(path, f"{hive_id}/{path.relative_to(folder)}")
        if rows:
            cols = sorted({k for r in rows for k in r}, key=lambda k: (k not in ("date", "overall"), k))
            s = io.StringIO()
            w = csv.DictWriter(s, fieldnames=cols)
            w.writeheader()
            w.writerows(rows)
            z.writestr(f"{hive_id}/metrics.csv", s.getvalue())
        z.writestr(
            f"{hive_id}/README.txt",
            "HiveLens export\n"
            "metrics.csv      one row per inspection (all numbers are measured from SAM 3.1 masks)\n"
            "<date>/inspection.json  report, verified claims, agent trace\n"
            "<date>/*.jpg     original photos and overlays\n",
        )
    return buf.getvalue()
