"""Hive registry: every hive keeps its inspections on disk, so trends build up over time.

Layout:
  data/hives/farms.json                                 (farms: groups of hives on one site)
  data/hives/<hive_id>/hive.json                        (a hive, with its farm_id)
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


def create_hive(name: str, location: str = "", farm_id: str | None = None) -> dict:
    if farm_id is not None and get_farm(farm_id) is None:
        raise ValueError(f"Unknown farm: {farm_id}")
    base = _slug(name)
    hive_id, n = base, 2
    while _hive_dir(hive_id).exists():
        hive_id, n = f"{base}-{n}", n + 1
    hive = {"id": hive_id, "name": name, "location": location, "farm_id": farm_id,
            "created": datetime.now().isoformat(timespec="seconds")}
    _hive_dir(hive_id).mkdir(parents=True, exist_ok=True)
    (_hive_dir(hive_id) / "hive.json").write_text(json.dumps(hive, indent=2))
    return hive


def set_hive_farm(hive_id: str, farm_id: str | None) -> dict:
    if farm_id is not None and get_farm(farm_id) is None:
        raise ValueError(f"Unknown farm: {farm_id}")
    path = _hive_dir(hive_id) / "hive.json"
    hive = json.loads(path.read_text())
    hive["farm_id"] = farm_id
    path.write_text(json.dumps(hive, indent=2))
    return hive


HIVE_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")
YARD_LIMIT_M = 500.0


def update_hive(hive_id: str, **fields) -> dict:
    """Sets yard position (x_m, y_m, in metres) and paint colour ("#rrggbb"). None clears a field."""
    path = _hive_dir(hive_id) / "hive.json"
    hive = json.loads(path.read_text())
    for key, value in fields.items():
        if key in ("x_m", "y_m"):
            if value is not None:
                value = float(value)
                if not -YARD_LIMIT_M <= value <= YARD_LIMIT_M:
                    raise ValueError("A hive must stay within 500 m of the yard origin.")
                value = round(value, 2)
        elif key == "color":
            if value is not None and not HIVE_COLOR.match(str(value)):
                raise ValueError("Colour must look like #e9c46a.")
        else:
            raise ValueError(f"Unknown hive field: {key}")
        if value is None:
            hive.pop(key, None)
        else:
            hive[key] = value
    path.write_text(json.dumps(hive, indent=2))
    return hive


# ── Farms ──────────────────────────────────────────────────────────────
# A farm is one site (apiary) with its own yard. Hives belong to at most one farm.

def _farms_path() -> Path:
    return config.HIVES_DIR / "farms.json"


def list_farms() -> list[dict]:
    path = _farms_path()
    return json.loads(path.read_text()) if path.exists() else []


def get_farm(farm_id: str) -> dict | None:
    return next((f for f in list_farms() if f["id"] == farm_id), None)


def create_farm(name: str, location: str = "") -> dict:
    farms = list_farms()
    taken = {f["id"] for f in farms}
    base = _slug(name) if _slug(name) != "hive" else "farm"
    farm_id, n = base, 2
    while farm_id in taken:
        farm_id, n = f"{base}-{n}", n + 1
    farm = {"id": farm_id, "name": name, "location": location, "created": datetime.now().isoformat(timespec="seconds")}
    config.HIVES_DIR.mkdir(parents=True, exist_ok=True)
    _farms_path().write_text(json.dumps([*farms, farm], indent=2))
    return farm


FARM_FIELDS = ("name", "location", "maps_url", "breed", "lat", "lon", "place", "country_code", "elevation_m")


def update_farm(farm_id: str, **fields) -> dict:
    """Changes the given farm fields (see FARM_FIELDS); None clears a field."""
    farms = list_farms()
    farm = next((f for f in farms if f["id"] == farm_id), None)
    if farm is None:
        raise ValueError(f"Unknown farm: {farm_id}")
    for key, value in fields.items():
        if key not in FARM_FIELDS:
            raise ValueError(f"Unknown farm field: {key}")
        if value is None:
            farm.pop(key, None)
        else:
            farm[key] = value
    _farms_path().write_text(json.dumps(farms, indent=2))
    return farm


def ensure_farm(name: str, location: str = "") -> dict:
    """The farm with this name, created if it does not exist yet."""
    return next((f for f in list_farms() if f["name"] == name), None) or create_farm(name, location)


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
