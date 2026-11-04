"""Usage log for paid model calls, and what they cost.

Every call to the Meta Model API goes through `meta_client.client()`, which records
one line per call in data/usage.jsonl: when, which model, tokens in and out, and
the job it belonged to (an inspection or a benchmark run). Answers served from the
disk cache never reach the API, so they are not recorded and cost nothing.
Prices live in the settings, so a new price list re-prices the whole history.
"""

from __future__ import annotations

import json
import threading
import time
from datetime import date, datetime, timedelta

from . import config

_lock = threading.Lock()
_context: dict = {}


def _log_path():
    return config.DATA_DIR / "usage.jsonl"


def set_context(**fields) -> None:
    """Tags the following calls with a job (job_id, kind, hive_id, label). Shared across worker threads."""
    with _lock:
        _context.clear()
        _context.update({k: v for k, v in fields.items() if v is not None})


def clear_context() -> None:
    with _lock:
        _context.clear()


def _num(obj, *names) -> int:
    """First integer field found on an SDK usage object or dict."""
    for name in names:
        value = obj.get(name) if isinstance(obj, dict) else getattr(obj, name, None)
        if isinstance(value, (int, float)):
            return int(value)
    return 0


def _detail(obj, outer: str, inner: str) -> int:
    part = obj.get(outer) if isinstance(obj, dict) else getattr(obj, outer, None)
    return _num(part, inner) if part is not None else 0


def record(model: str, kind: str, usage_obj=None, ok: bool = True) -> dict:
    """Appends one call to the log. `usage_obj` is the SDK's usage (chat or responses API) or None."""
    u = usage_obj or {}
    entry = {
        "ts": round(time.time(), 3),
        "model": model,
        "kind": kind,  # "reasoning" (Muse Spark) or "segmentation" (SAM 3.1)
        "input_tokens": _num(u, "prompt_tokens", "input_tokens"),
        "output_tokens": _num(u, "completion_tokens", "output_tokens"),
        "cached_tokens": _detail(u, "prompt_tokens_details", "cached_tokens") or _detail(u, "input_tokens_details", "cached_tokens"),
        "reasoning_tokens": _detail(u, "completion_tokens_details", "reasoning_tokens") or _detail(u, "output_tokens_details", "reasoning_tokens"),
        "ok": ok,
    }
    with _lock:
        entry.update(_context)
        path = _log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")
    return entry


def read_all() -> list[dict]:
    path = _log_path()
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue  # a half-written last line after a crash
    return rows


# ── Cost ────────────────────────────────────────────────────────────────

def call_cost(row: dict, prices: dict) -> float:
    """USD for one call. Reasoning: per million tokens (cached input at its own rate).
    Segmentation: a flat price per request plus optional per-token prices."""
    if not row.get("ok", True):
        return 0.0
    if row.get("kind") == "segmentation":
        p = prices["sam"]
        return (p["per_request"]
                + row.get("input_tokens", 0) * p["input_per_m"] / 1e6
                + row.get("output_tokens", 0) * p["output_per_m"] / 1e6)
    p = prices["muse"]
    cached = min(row.get("cached_tokens", 0), row.get("input_tokens", 0))
    fresh = row.get("input_tokens", 0) - cached
    return (fresh * p["input_per_m"] + cached * p["cached_per_m"] + row.get("output_tokens", 0) * p["output_per_m"]) / 1e6


def _blank() -> dict:
    return {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cached_tokens": 0, "cost": 0.0}


def _add(acc: dict, row: dict, cost: float) -> None:
    acc["calls"] += 1
    for k in ("input_tokens", "output_tokens", "cached_tokens"):
        acc[k] += row.get(k, 0)
    acc["cost"] += cost


def _cache_counts() -> dict:
    """Answers already on disk. Re-running them is free, so they show what caching saves."""
    cache = config.CACHE_DIR

    def count(sub: str) -> int:
        d = cache / sub
        return sum(1 for _ in d.glob("*.json")) if d.exists() else 0

    return {"sam": count("sam"), "muse": sum(count(s) for s in ("muse_votes", "muse_tiles", "naive_muse"))}


def summary(prices: dict, hive_count: int, inspections_per_month: float, today: date | None = None) -> dict:
    """Everything the usage page shows, priced with the current settings."""
    today = today or date.today()
    month_start = today.replace(day=1)
    rows = read_all()
    totals = {"all": _blank(), "month": _blank(), "today": _blank()}
    by_model: dict[tuple[str, str], dict] = {}
    by_job: dict[str, dict] = {}
    daily: dict[str, float] = {}

    for row in rows:
        cost = call_cost(row, prices)
        day = datetime.fromtimestamp(row["ts"]).date()
        _add(totals["all"], row, cost)
        if day >= month_start:
            _add(totals["month"], row, cost)
        if day == today:
            _add(totals["today"], row, cost)
        key = (row.get("model", "?"), row.get("kind", "reasoning"))
        _add(by_model.setdefault(key, {"model": key[0], "kind": key[1], **_blank()}), row, cost)
        daily[day.isoformat()] = daily.get(day.isoformat(), 0.0) + cost
        # Calls outside an app job (scripts such as the benchmark CLI) are grouped per day.
        job = row.get("job_id") or f"other-{day.isoformat()}"
        j = by_job.setdefault(job, {
            "job_id": job, "kind": row.get("job_kind", "inspection") if row.get("job_id") else "other",
            "hive_id": row.get("hive_id"),
            "label": row.get("label", "") if row.get("job_id") else f"Outside the app (scripts), {day.isoformat()}",
            "started": row["ts"], "segmentation": 0, "reasoning": 0, **_blank()})
        _add(j, row, cost)
        j[row.get("kind", "reasoning")] = j.get(row.get("kind", "reasoning"), 0) + 1
        j["started"] = min(j["started"], row["ts"])

    jobs = sorted(by_job.values(), key=lambda j: j["started"], reverse=True)
    inspections = [j for j in jobs if j["kind"] == "inspection"]
    avg = sum(j["cost"] for j in inspections) / len(inspections) if inspections else None
    days = [(today - timedelta(days=i)).isoformat() for i in range(29, -1, -1)]
    cache = _cache_counts()
    return {
        "prices": prices,
        "totals": totals,
        "by_model": sorted(by_model.values(), key=lambda m: m["cost"], reverse=True),
        "jobs": jobs[:25],
        "daily": [{"date": d, "cost": round(daily.get(d, 0.0), 6)} for d in days],
        "per_inspection": avg,
        "inspections_priced": len(inspections),
        "projection": {
            "hives": hive_count,
            "inspections_per_month": inspections_per_month,
            "monthly_cost": None if avg is None else avg * hive_count * inspections_per_month,
        },
        "cache": {**cache, "sam_value": cache["sam"] * prices["sam"]["per_request"]},
        "tracking_since": rows[0]["ts"] if rows else None,
    }
