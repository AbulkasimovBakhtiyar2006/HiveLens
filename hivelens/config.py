"""Settings for HiveLens. Everything can be overridden with environment variables or a .env file."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path) -> None:
    """Tiny .env reader so the project has no extra dependency for it."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv(ROOT / ".env")

API_BASE = os.getenv("META_API_BASE", "https://api.meta.ai/v1")
API_KEY = os.getenv("MODEL_API_KEY", "")
REASONING_MODEL = os.getenv("HIVELENS_REASONING_MODEL", "muse-spark-1.3")
SEGMENT_MODEL = os.getenv("HIVELENS_SEGMENT_MODEL", "sam-3.1")
REASONING_EFFORT = os.getenv("HIVELENS_REASONING_EFFORT", "medium")
# Public browser credential, deliberately separate from the private model API key.
# Restrict it to HTTP referrers and Maps JavaScript API in Google Cloud.
GOOGLE_MAPS_BROWSER_KEY = os.getenv("GOOGLE_MAPS_BROWSER_KEY", "")
GOOGLE_MAPS_MAP_ID = os.getenv("GOOGLE_MAPS_MAP_ID", "")

DATA_DIR = Path(os.getenv("HIVELENS_DATA_DIR", ROOT / "data"))
CACHE_DIR = DATA_DIR / "cache"
HIVES_DIR = DATA_DIR / "hives"
AUTH_USER = os.getenv("HIVELENS_AUTH_USER", "judge")
AUTH_PASSWORD = os.getenv("HIVELENS_AUTH_PASSWORD", "")
PUBLIC_READ = os.getenv("HIVELENS_PUBLIC_READ", "0") == "1"
REQUIRE_AUTH = os.getenv("HIVELENS_REQUIRE_AUTH", "0") == "1"
SECURE_COOKIES = os.getenv("HIVELENS_SECURE_COOKIES", "0") == "1"


def has_api_key() -> bool:
    return bool(API_KEY)


@dataclass(frozen=True)
class Thresholds:
    """Default decision thresholds.

    These are starting points, not veterinary rules: mite-drop thresholds differ by
    season, region and colony size, so beekeepers are expected to tune them.
    """

    # natural mite drop on a sticky board, mites per day
    mites_per_day_moderate: float = 3.0
    mites_per_day_high: float = 10.0
    # stores, in weeks of food at the assumed consumption rate
    stores_weeks_low: float = 3.0
    stores_weeks_ok: float = 6.0
    # a full deep frame of capped honey (both sides), kg
    honey_kg_full_frame: float = 3.0
    # assumed colony consumption, kg per week
    consumption_kg_week: float = 1.0
    # relative tolerance when a claim says "about X"
    approx_tolerance: float = 0.25


THRESHOLDS = Thresholds()
