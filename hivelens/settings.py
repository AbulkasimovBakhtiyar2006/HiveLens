"""User settings kept on disk (data/settings.json): profile, model prices, budget.

The API key is never stored here; it stays in .env.
"""

from __future__ import annotations

import copy
import json
import math
import time

from . import config

# Muse Spark: $1.25 input, $0.15 cached input, $4.25 output per million tokens, as reported
# for Meta's paid API (Muse Spark 1.1 to 1.3). Meta has not published a SAM 3.1 API price;
# $0.005 per request matches a public SAM 3 image host and is only a placeholder.
DEFAULTS = {
    "profile": {"name": "", "email": "", "organisation": "", "role": "beekeeper", "photo_version": 0},
    "prices": {
        "muse": {"input_per_m": 1.25, "cached_per_m": 0.15, "output_per_m": 4.25},
        "sam": {"per_request": 0.005, "input_per_m": 0.0, "output_per_m": 0.0},
    },
    "planning": {"inspections_per_hive_month": 4, "monthly_budget": 0},
}
ROLES = ("beekeeper", "owner", "researcher", "inspector")


def _path():
    return config.DATA_DIR / "settings.json"


def _merge(base: dict, extra: dict) -> dict:
    out = copy.deepcopy(base)
    for key, value in (extra or {}).items():
        if key in out and isinstance(out[key], dict) and isinstance(value, dict):
            out[key] = _merge(out[key], value)
        elif key in out:
            out[key] = value
    return out


def load() -> dict:
    path = _path()
    saved = json.loads(path.read_text()) if path.exists() else {}
    return _merge(DEFAULTS, saved)


def photo_path():
    return config.DATA_DIR / "profile.jpg"


def set_photo(image) -> dict:
    """Saves a square 256 px profile photo (PIL image), or removes it when image is None."""
    from PIL import ImageOps

    path = photo_path()
    settings = load()
    if image is None:
        path.unlink(missing_ok=True)
        settings["profile"]["photo_version"] = 0
    else:
        square = ImageOps.fit(ImageOps.exif_transpose(image).convert("RGB"), (256, 256))
        path.parent.mkdir(parents=True, exist_ok=True)
        square.save(path, "JPEG", quality=88)
        settings["profile"]["photo_version"] = int(time.time())
    _path().write_text(json.dumps(settings, indent=2))
    return settings


def _price(value, field: str, top: float = 1000.0) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field} must be a number.") from None
    if not math.isfinite(v) or not 0 <= v <= top:
        raise ValueError(f"{field} must be between 0 and {top:g}.")
    return v


def save(update: dict) -> dict:
    """Validates a partial update, merges it into the saved settings and returns the result."""
    current = load()
    merged = _merge(current, update if isinstance(update, dict) else {})
    p = merged["profile"]
    p["photo_version"] = current["profile"]["photo_version"]  # only set_photo() changes it
    for key, limit in (("name", 100), ("email", 200), ("organisation", 120)):
        p[key] = str(p.get(key) or "").strip()
        if len(p[key]) > limit:
            raise ValueError(f"The {key} is too long.")
    if p["email"] and ("@" not in p["email"] or " " in p["email"]):
        raise ValueError("Enter a valid email address, or leave it empty.")
    if p["role"] not in ROLES:
        raise ValueError("Choose a role from the list.")
    for model, fields in merged["prices"].items():
        for key in fields:
            fields[key] = _price(fields[key], f"{model} {key.replace('_', ' ')}")
    plan = merged["planning"]
    plan["inspections_per_hive_month"] = _price(plan["inspections_per_hive_month"], "Inspections per month", 60)
    plan["monthly_budget"] = _price(plan["monthly_budget"], "Monthly budget", 1_000_000)
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(merged, indent=2))
    return merged
