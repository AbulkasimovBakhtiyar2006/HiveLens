"""Rules and claim verification. Plain Python, no models.

The agent (Muse Spark) may say anything it likes while it reasons, but a
statement only reaches the final report if `verify_claim` confirms it against
the measured numbers.
"""

from __future__ import annotations

from statistics import mean

from .config import THRESHOLDS

LEVEL_ORDER = {"unknown": 0, "good": 1, "watch": 2, "act": 3}


def aggregate(varroa: dict | None, combs: list[dict], frames_in_hive: int | None) -> dict:
    """Flattens per-photo measurements into one metrics dict for an inspection."""
    m: dict = {}
    if varroa:
        m.update(varroa)
    if combs:
        for key in ("honey_pct", "brood_pct", "larvae_pct", "pollen_pct", "empty_pct", "bees_pct"):
            vals = [c[key] for c in combs if key in c]
            if vals:
                m[key] = round(mean(vals), 1)
        m["sides_photographed"] = len(combs)
        per_side = mean(c["honey_kg_this_side"] for c in combs)
        m["honey_kg_photographed"] = round(sum(c["honey_kg_this_side"] for c in combs), 2)
        frames = frames_in_hive or max(1, round(len(combs) / 2))
        m["frames_in_hive"] = frames
        m["honey_kg_hive_est"] = round(per_side * 2 * frames, 1)
        m["stores_weeks"] = round(m["honey_kg_hive_est"] / THRESHOLDS.consumption_kg_week, 1)
        m["brood_total_pct"] = round(m.get("brood_pct", 0) + m.get("larvae_pct", 0), 1)
    return m


def add_trends(metrics: dict, previous: dict | None) -> dict:
    if not previous:
        return metrics
    out = dict(metrics)
    for key in ("mites_per_day", "honey_kg_hive_est", "brood_total_pct"):
        if key in metrics and key in previous:
            out[f"{key}_change"] = round(metrics[key] - previous[key], 2)
    return out


def assess(metrics: dict) -> dict:
    """Traffic-light levels decided by rules, so the agent cannot invent a status."""
    t = THRESHOLDS
    levels: dict[str, str] = {}
    flags: list[str] = []

    mpd = metrics.get("mites_per_day")
    if mpd is None:
        levels["varroa"] = "unknown"
    elif mpd >= t.mites_per_day_high:
        levels["varroa"] = "act"
        flags.append(f"Mite drop {mpd}/day is at or above the high threshold ({t.mites_per_day_high}/day).")
    elif mpd >= t.mites_per_day_moderate:
        levels["varroa"] = "watch"
        flags.append(f"Mite drop {mpd}/day is above the watch threshold ({t.mites_per_day_moderate}/day).")
    else:
        levels["varroa"] = "good"

    if metrics.get("mites_per_day_change", 0) > 0 and levels["varroa"] != "good":
        flags.append("Mite drop is rising since the previous inspection.")

    weeks = metrics.get("stores_weeks")
    if weeks is None:
        levels["stores"] = "unknown"
    elif weeks < t.stores_weeks_low:
        levels["stores"] = "act"
        flags.append(f"Estimated stores cover only {weeks} weeks.")
    elif weeks < t.stores_weeks_ok:
        levels["stores"] = "watch"
    else:
        levels["stores"] = "good"

    brood = metrics.get("brood_total_pct")
    if brood is None:
        levels["brood"] = "unknown"
    elif brood < 5:
        levels["brood"] = "watch"
        flags.append("Little or no brood visible on the photographed sides.")
    else:
        levels["brood"] = "good"

    overall = max(levels.values(), key=lambda v: LEVEL_ORDER[v]) if levels else "unknown"
    return {"levels": levels, "overall": overall, "flags": flags}


# ── claim verification ────────────────────────────────────────────────────────

OPS = (">", ">=", "<", "<=", "about", "between")


def verify_claim(claim: dict, metrics: dict) -> dict:
    metric = str(claim.get("metric", ""))
    op = str(claim.get("op", ""))
    result = {**claim, "actual": metrics.get(metric)}

    if metric not in metrics:
        return {**result, "verdict": "unverifiable",
                "reason": f"No measurement called '{metric}'. Known: {sorted(metrics)}"}
    if op not in OPS:
        return {**result, "verdict": "unverifiable", "reason": f"op must be one of {OPS}"}
    try:
        value = float(claim["value"])
        actual = float(metrics[metric])
    except (KeyError, TypeError, ValueError):
        return {**result, "verdict": "unverifiable", "reason": "value must be a number"}

    if op == ">":
        ok = actual > value
    elif op == ">=":
        ok = actual >= value
    elif op == "<":
        ok = actual < value
    elif op == "<=":
        ok = actual <= value
    elif op == "between":
        try:
            hi = float(claim["value_max"])
        except (KeyError, TypeError, ValueError):
            return {**result, "verdict": "unverifiable", "reason": "between needs value_max"}
        ok = value <= actual <= hi
    else:  # about
        tol = max(abs(value) * THRESHOLDS.approx_tolerance, 1.0)
        ok = abs(actual - value) <= tol

    return {**result, "verdict": "verified" if ok else "rejected",
            "reason": f"measured {metric} = {actual}"}
