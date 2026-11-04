"""HiveLens Fast Web UI & API Server.

Replaces the laggy Streamlit wrapper with a zero-dependency multi-threaded HTTP + SSE
server that loads in <50ms, caches 49MP board previews, and streams live SAM 3.1 /
Muse Spark agent events in real time.

Run with:
    python server.py        # http://127.0.0.1:8502 (the Streamlit app keeps 8501)
"""

from __future__ import annotations

import base64
import io
import json
import math
import sys
import threading
import time
import urllib.parse
import uuid
import webbrowser
from datetime import date, timedelta
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from PIL import Image, ImageOps

from hivelens import __version__, commons, config, engine, place, settings, store, usage
from hivelens.viz import CLASS_COLORS, CLASS_LABELS

Image.MAX_IMAGE_PIXELS = None  # sticky-board photos are ~49 MP

PORT = int(config.os.getenv("HIVELENS_PORT", "8502"))
HOST = "127.0.0.1"
UI_PATH = Path(__file__).resolve().parent / "hivelens" / "ui.html"
STATIC_DIR = UI_PATH.parent / "static"
MAX_REQUEST_BYTES = 85 * 1024 * 1024  # 60 MB of photos after base64 encoding

# ── In-memory caches & live job store ─────────────────────────────────────────

_SAMPLE_CACHE: dict | None = None
_THUMB_CACHE: dict[str, bytes] = {}
_JOBS: dict[str, dict] = {}
_JOBS_LOCK = threading.Lock()


def _safe_part(part: str) -> bool:
    """One path segment from a URL: no traversal, no separators, no hidden files."""
    return bool(part) and part not in (".", "..") and "/" not in part and "\\" not in part and not part.startswith(".")


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def open_image_bytes(raw: bytes) -> Image.Image:
    return ImageOps.exif_transpose(Image.open(io.BytesIO(raw))).convert("RGB")


def open_image_path(path: Path) -> Image.Image:
    return ImageOps.exif_transpose(Image.open(path)).convert("RGB")


def get_samples(force: bool = False) -> dict:
    """Caches dataset file listings so the UI never lags scanning disk."""
    global _SAMPLE_CACHE
    if _SAMPLE_CACHE is not None and not force:
        return _SAMPLE_CACHE

    varroa_dir = config.DATA_DIR / "varroa"
    boards = []
    if varroa_dir.exists():
        xml_map = {p.stem: p for p in varroa_dir.rglob("*.xml")}
        for p in sorted(varroa_dir.rglob("images/*.jpg")):
            xml = xml_map.get(p.stem)
            experts = xml.read_text().count("<object>") if xml and xml.exists() else None
            boards.append({"name": p.name, "path": str(p), "experts": experts})

    comb_dir = config.DATA_DIR / "demo" / "comb"
    frames = []
    if comb_dir.exists():
        for p in sorted(comb_dir.glob("*")):
            if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"):
                frames.append({"name": p.name, "path": str(p)})

    _SAMPLE_CACHE = {"boards": boards, "frames": frames}
    return _SAMPLE_CACHE


BREEDS = ("carnica", "ligustica", "buckfast", "caucasica", "mellifera", "carpatica", "local")


def farm_fields(body: dict) -> dict:
    """Validated farm fields from a request body. Raises ValueError with a message for the user."""
    name = str(body.get("name", "")).strip()
    loc = str(body.get("location", "")).strip()
    maps = str(body.get("maps_url", "")).strip()
    breed = str(body.get("breed", "")).strip()
    if not name or len(name) > 100:
        raise ValueError("Enter a farm name (up to 100 characters).")
    if len(loc) > 200 or len(maps) > 2000:
        raise ValueError("The location or map link is too long.")
    if breed and breed not in BREEDS:
        raise ValueError("Choose a bee breed from the list.")
    return {"name": name, "location": loc, "maps_url": maps, "breed": breed}


def locate_farm(fields: dict) -> tuple[dict, str | None]:
    """Adds coordinates from the map link or place name. Returns the fields and a warning, if any."""
    geo = {"lat": None, "lon": None, "place": None, "country_code": None, "elevation_m": None}
    if not (fields["location"] or fields["maps_url"]):
        return {**fields, **geo}, None
    try:
        hit = place.resolve(fields["location"], fields["maps_url"])
    except Exception:
        return {**fields, **geo}, "The map service did not answer, so the farm was saved without weather. Save it again later."
    if not hit:
        return {**fields, **geo}, "That place was not found. Paste a Google Maps link to show the weather."
    return {**fields, **{k: hit.get(k) for k in geo}}, None


def build_apiary_overview() -> dict:
    """Every hive with its latest numbers, laid out per farm, plus mite-drift links inside each farm."""
    hives = store.list_hives()
    farms = store.list_farms()
    farm_ids = {f["id"] for f in farms}
    nodes = []

    # Each farm gets its own yard grid; hives without a known farm share an "unassigned" yard.
    groups: dict[str | None, list[dict]] = {}
    for h in hives:
        groups.setdefault(h.get("farm_id") if h.get("farm_id") in farm_ids else None, []).append(h)
    placed = []
    for farm_id, members in groups.items():
        cols = max(2, math.ceil(math.sqrt(len(members))))  # a compact hex block per farm
        placed += [(farm_id, i, cols, h) for i, h in enumerate(members)]

    for farm_id, idx, cols, h in placed:
        insps = [record for record in store.inspections(h["id"]) if not record.get("demo_capture")]
        latest = insps[-1] if insps else None
        prev = insps[-2] if len(insps) >= 2 else None

        metrics = latest.get("metrics", {}) if latest else {}
        status = latest.get("status", {}) if latest else {"overall": "unknown", "levels": {}, "flags": []}
        overall = status.get("overall", "unknown")

        mpd = metrics.get("mites_per_day")
        mpd_change = metrics.get("mites_per_day_change")
        if mpd_change is None and latest and prev:
            if "mites_per_day" in metrics and "mites_per_day" in prev.get("metrics", {}):
                mpd_change = round(metrics["mites_per_day"] - prev["metrics"]["mites_per_day"], 2)

        # Trend classification: improving / worsening / stable
        trend = "stable"
        if mpd_change is not None:
            if mpd_change <= -0.5:
                trend = "improving"
            elif mpd_change >= 0.5:
                trend = "worsening"

        row = idx // cols
        col = idx % cols
        # A position the beekeeper placed on the yard map wins; otherwise a staggered
        # default grid (2.5 m between hives, 2.2 m between rows) until they place it.
        placed = h.get("x_m") is not None and h.get("y_m") is not None
        x_m = h["x_m"] if placed else col * 2.5 + (1.25 if row % 2 else 0.0)
        y_m = h["y_m"] if placed else row * 2.2

        nodes.append({
            "id": h["id"],
            "name": h["name"],
            "farm_id": farm_id,
            "placed": placed,
            "color": h.get("color"),
            "location": h.get("location", "Talgar Apiary"),
            "row": row,
            "col": col,
            "x_m": round(x_m, 2),
            "y_m": round(y_m, 2),
            "inspection_count": len(insps),
            "synthetic": bool(latest and latest.get("synthetic")),
            "latest_date": latest.get("date") if latest else None,
            "overall": overall,
            "levels": status.get("levels", {}),
            "flags": status.get("flags", []),
            "mites_per_day": mpd,
            "mites_per_day_change": mpd_change,
            "honey_pct": metrics.get("honey_pct"),
            "brood_total_pct": metrics.get("brood_total_pct"),
            "stores_weeks": metrics.get("stores_weeks"),
            "honey_kg_hive_est": metrics.get("honey_kg_hive_est"),
            "trend": trend,
            "drift_risk_from": [],
        })

    # Compute Varroa mite drift / epidemiological contagion links between nearby hives
    drift_links = []
    # Only a high mite drop makes a hive a source: drifting and robbing bees carry mites to
    # neighbours. A hive that is critical for another reason (low stores) does not spread mites.
    sources = [n for n in nodes if (n["mites_per_day"] or 0) >= config.THRESHOLDS.mites_per_day_high]
    for src in sources:
        for dst in nodes:
            if src["id"] == dst["id"] or src["farm_id"] != dst["farm_id"]:
                continue
            dist = math.hypot(src["x_m"] - dst["x_m"], src["y_m"] - dst["y_m"])
            if dist <= 4.0:  # Adjacent hive foraging/drifting zone
                risk = "high" if dist <= 2.8 else "moderate"
                dst["drift_risk_from"].append({"id": src["id"], "name": src["name"], "mites_per_day": src["mites_per_day"], "risk": risk})
                drift_links.append({
                    "from_id": src["id"],
                    "from_name": src["name"],
                    "to_id": dst["id"],
                    "to_name": dst["name"],
                    "distance_m": round(dist, 1),
                    "risk": risk,
                })

    summary = {
        "total_hives": len(nodes),
        "good": sum(1 for n in nodes if n["overall"] == "good"),
        "watch": sum(1 for n in nodes if n["overall"] == "watch"),
        "act": sum(1 for n in nodes if n["overall"] == "act"),
        "improving": sum(1 for n in nodes if n["trend"] == "improving"),
        "worsening": sum(1 for n in nodes if n["trend"] == "worsening"),
        "at_drift_risk": sum(1 for n in nodes if n["drift_risk_from"]),
    }
    farm_rows = []
    for f in [*farms, {"id": None, "name": "Unassigned", "location": ""}]:
        members = [n for n in nodes if n["farm_id"] == f["id"]]
        if f["id"] is None and not members:
            continue
        counts = {k: sum(1 for n in members if n["overall"] == k) for k in ("good", "watch", "act", "unknown")}
        worst = next((k for k in ("act", "watch", "good") if counts[k]), "unknown")
        farm_rows.append({**f, "hive_count": len(members), "counts": counts, "overall": worst})
    return {"summary": summary, "hives": nodes, "drift_links": drift_links, "farms": farm_rows}


def seed_demo_apiary() -> dict:
    """Creates a SYNTHETIC multi-hive apiary to preview the Apiary Map.

    These numbers are made up (no photos, no SAM, no Muse Spark). Every hive is named
    "(synthetic)" and every record carries "synthetic": true so it is never mistaken
    for a measured inspection.
    """
    scenarios = [
        ("Hive #01 · Queen Alma", "Talgar Mountain Sector A", [
            (1.2, 48, 32, 8, 9.5, "Baseline healthy colony"),
            (1.4, 52, 34, 9, 10.2, "Strong foraging week"),
            (1.1, 56, 35, 10, 11.0, "Capped honey stores expanding"),
        ]),
        ("Hive #02 · Tien-Shan Gold", "Talgar Mountain Sector A", [
            (2.0, 44, 30, 7, 8.8, "Normal mite drop"),
            (4.8, 41, 28, 6, 8.2, "Varroa drop crossed watch threshold"),
            (7.5, 38, 25, 6, 7.6, "Rising mite trend — schedule treatment"),
        ]),
        ("Hive #03 · Hotspot Alpha", "Talgar Mountain Sector A", [
            (4.2, 39, 29, 6, 7.8, "Elevated mite count on sticky board"),
            (9.6, 34, 24, 5, 6.8, "Rapid Varroa reproduction"),
            (16.4, 29, 19, 4, 5.8, "CRITICAL outbreak: 16.4 mites/day, drift risk to neighbors"),
        ]),
        ("Hive #04 · East Ridge", "Talgar Mountain Sector A", [
            (1.5, 45, 31, 8, 9.0, "Healthy colony next to Hive #03"),
            (2.9, 43, 29, 7, 8.6, "Slight uptick near Hotspot Alpha"),
            (5.4, 40, 27, 7, 8.0, "Mite drift detected from adjacent Hive #03"),
        ]),
        ("Hive #05 · Treated Recovery", "Talgar Mountain Sector B", [
            (14.2, 35, 22, 5, 7.0, "High infestation — formic acid treatment applied"),
            (6.8, 39, 26, 7, 7.8, "Post-treatment drop falling rapidly"),
            (1.8, 46, 31, 9, 9.2, "Colony recovered — mite drop back to safe level"),
        ]),
        ("Hive #06 · Medeu Meadow", "Talgar Mountain Sector B", [
            (0.8, 55, 36, 11, 11.0, "Clean sticky board, strong brood pattern"),
            (0.9, 58, 37, 11, 11.6, "Peak nectar flow"),
            (0.7, 62, 38, 12, 12.4, "Ready for winter stores"),
        ]),
        ("Hive #07 · Late Swarm", "Talgar Mountain Sector B", [
            (1.9, 18, 22, 4, 3.6, "Small late-season colony, low honey stores"),
            (2.1, 15, 20, 4, 3.0, "Stores dropping — watch feeding"),
            (2.4, 11, 18, 3, 2.2, "Low winter stores (2.2 weeks) — supplemental feeding needed"),
        ]),
        ("Hive #08 · Foothill Guard", "Talgar Mountain Sector B", [
            (8.5, 42, 27, 7, 8.4, "Moderate-high mites before thymol strip"),
            (4.1, 44, 29, 8, 8.8, "Responding well to treatment"),
            (2.2, 47, 32, 9, 9.4, "Stabilized below watch threshold"),
        ]),
    ]

    farm_for = {
        "Talgar Mountain Sector A": store.ensure_farm("Talgar North", "Talgar Mountain, sector A"),
        "Talgar Mountain Sector B": store.ensure_farm("Talgar South", "Talgar Mountain, sector B"),
    }
    existing = {h["name"]: h for h in store.list_hives()}
    created = 0
    today = date.today()

    for name, loc, weeks in scenarios:
        name = f"{name} (synthetic)"
        farm_id = farm_for[loc]["id"]
        if name in existing:
            if not existing[name].get("farm_id"):
                store.set_hive_farm(existing[name]["id"], farm_id)
            continue
        h = store.create_hive(name, "synthetic demo", farm_id)
        created += 1
        prev_metrics = None
        for w_idx, (mpd, honey_pct, brood_pct, larvae_pct, honey_kg, note) in enumerate(weeks):
            d_str = (today - timedelta(weeks=(len(weeks) - 1 - w_idx))).isoformat()
            days = 3.0
            mite_count = int(round(mpd * days))
            varroa_m = {
                "mite_count": mite_count,
                "days_on_board": days,
                "mites_per_day": mpd,
                "rejected_detections": 3 + (w_idx * 2),
            }
            comb_m = [{
                "honey_pct": float(honey_pct),
                "brood_pct": float(brood_pct),
                "larvae_pct": float(larvae_pct),
                "pollen_pct": 8.0,
                "empty_pct": max(0.0, 100.0 - honey_pct - brood_pct - larvae_pct - 18.0),
                "bees_pct": 10.0,
                "honey_kg_this_side": round(honey_kg / 20.0, 2),
            }]
            metrics = engine.add_trends(engine.aggregate(varroa_m, comb_m, 10), prev_metrics)
            status = engine.assess(metrics)
            prev_metrics = metrics

            c1 = engine.verify_claim({"statement": f"Mite drop is around {mpd}/day", "metric": "mites_per_day", "op": "about", "value": mpd}, metrics)
            c1["id"] = "c1"
            c2 = engine.verify_claim({"statement": f"Capped honey covers about {honey_pct}% of comb", "metric": "honey_pct", "op": "about", "value": honey_pct}, metrics)
            c2["id"] = "c2"

            urgency = "now" if status["overall"] == "act" else ("this_week" if status["overall"] == "watch" else "next_inspection")
            action_txt = (
                "Apply targeted Varroa treatment & isolate adjacent drift risk"
                if status["levels"].get("varroa") == "act"
                else "Feed 2:1 sugar syrup to boost winter stores"
                if status["levels"].get("stores") == "act"
                else "Monitor sticky board in 7 days"
            )
            record = {
                "date": d_str,
                "created": f"{d_str}T12:00:00",
                "synthetic": True,
                "models": {"segmentation": "synthetic (no model run)", "reasoning": "synthetic (no model run)"},
                "inputs": {"days_on_board": days, "frames_in_hive": 10, "note": note},
                "metrics": metrics,
                "per_photo": {"board": varroa_m, "frame_1": comb_m[0]},
                "detections": {},
                "status": status,
                "claims": [c1, c2],
                "report": {
                    "summary": f"[SYNTHETIC DEMO DATA — not measured] {note}. {mpd} mites/day ({mite_count} mites over {int(days)} days) and {metrics['stores_weeks']} weeks of estimated stores.",
                    "status": status,
                    "findings": [
                        {"text": f"Sticky board recorded {mpd} mites/day ({mite_count} total mites).", "claim_ids": ["c1"]},
                        {"text": f"Capped honey accounts for {honey_pct}% of visible comb ({metrics['honey_kg_hive_est']} kg hive estimate).", "claim_ids": ["c2"]},
                    ],
                    "actions": [{"action": action_txt, "urgency": urgency, "reason": f"Overall rule status: {status['overall']}"}],
                    "caveats": ["Synthetic demo record: numbers were typed in, not measured from photos."],
                    "discarded_findings": [],
                },
                "trace": [
                    {"type": "claim", **c1},
                    {"type": "claim", **c2},
                ],
            }
            store.save_inspection(h["id"], record, {}, {})

    return {"created": created, "apiary": build_apiary_overview()}


# ── Background Job Runners (Inspection & Benchmark) ───────────────────────────

def _push_job_event(job_id: str, event: dict) -> None:
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        if not job:
            return
        job["events"].append(event)
        if event.get("type") == "progress":
            job["progress"] = event.get("frac", job["progress"])
            job["message"] = event.get("msg", job["message"])


def _run_inspection_job(job_id: str, payload: dict) -> None:
    try:
        from hivelens.pipeline import run_inspection

        hive_id = payload["hive_id"]
        if not _safe_part(str(hive_id)) or not (config.HIVES_DIR / hive_id / "hive.json").exists():
            raise ValueError("unknown hive")
        hive_name = json.loads((config.HIVES_DIR / hive_id / "hive.json").read_text()).get("name", hive_id)
        usage.set_context(job_id=job_id, job_kind="inspection", hive_id=hive_id,
                          label=f"{hive_name}, {payload.get('date') or date.today().isoformat()}")
        insp_date = payload.get("date") or date.today().isoformat()
        days = float(payload.get("days_on_board", 3.0))
        frames_in_hive = int(payload.get("frames_in_hive", 10))
        note = str(payload.get("note", ""))
        use_agent = bool(payload.get("use_agent", True))
        board_refine = bool(payload.get("board_refine", True))

        frames: list[Image.Image] = []
        for b64 in payload.get("frames_b64") or []:
            raw = base64.b64decode(b64.split(",", 1)[-1])
            frames.append(open_image_bytes(raw))

        samples = get_samples()
        frame_map = {f["name"]: Path(f["path"]) for f in samples["frames"]}
        for fname in payload.get("frame_samples") or []:
            if fname in frame_map and frame_map[fname].exists():
                frames.append(open_image_path(frame_map[fname]))

        board: Image.Image | None = None
        if payload.get("board_b64"):
            raw = base64.b64decode(payload["board_b64"].split(",", 1)[-1])
            board = open_image_bytes(raw)
        elif payload.get("board_sample"):
            board_map = {b["name"]: Path(b["path"]) for b in samples["boards"]}
            bname = payload["board_sample"]
            if bname in board_map and board_map[bname].exists():
                board = open_image_path(board_map[bname])

        def on_progress(msg: str, frac: float):
            _push_job_event(job_id, {"type": "progress", "msg": msg, "frac": round(min(frac, 1.0), 3)})

        def on_event(ev: dict):
            _push_job_event(job_id, {"type": "agent_event", "event": ev})

        rec = run_inspection(
            hive_id,
            insp_date,
            frames=frames,
            board=board,
            days_on_board=days,
            frames_in_hive=frames_in_hive,
            note=note,
            use_agent=use_agent,
            board_refine=board_refine,
            capture_sources=payload.get("capture_sources") or {},
            progress=on_progress,
            on_event=on_event,
        )
        with _JOBS_LOCK:
            _JOBS[job_id]["status"] = "done"
            _JOBS[job_id]["result"] = rec
        _push_job_event(job_id, {"type": "done", "result": rec})
    except Exception as exc:
        with _JOBS_LOCK:
            _JOBS[job_id]["status"] = "error"
            _JOBS[job_id]["error"] = f"{type(exc).__name__}: {exc}"
        _push_job_event(job_id, {"type": "error", "error": f"{type(exc).__name__}: {exc}"})
    finally:
        usage.clear_context()


def _run_benchmark_job(job_id: str, payload: dict) -> None:
    try:
        import importlib.util

        spec = importlib.util.spec_from_file_location("eval_varroa", config.ROOT / "scripts" / "eval_varroa.py")
        ev_mod = importlib.util.module_from_spec(spec)
        if str(config.ROOT / "scripts") not in sys.path:
            sys.path.insert(0, str(config.ROOT / "scripts"))
        spec.loader.exec_module(ev_mod)

        n_boards = int(payload.get("n_boards", 12))
        skip = int(payload.get("skip", 8))
        usage.set_context(job_id=job_id, job_kind="benchmark", label=f"Benchmark, {n_boards} boards")
        use_muse = bool(payload.get("use_muse", True))

        def log(msg):
            _push_job_event(job_id, {"type": "log", "text": str(msg)})

        def progress(done, total):
            frac = min(done / max(1, total), 1.0)
            _push_job_event(job_id, {"type": "progress", "msg": f"Evaluating board {min(int(done) + 1, total)}/{total}", "frac": round(frac, 3)})

        res = ev_mod.evaluate(n_boards, skip, muse=use_muse, log=log, progress=progress)
        with _JOBS_LOCK:
            _JOBS[job_id]["status"] = "done"
            _JOBS[job_id]["result"] = res
        _push_job_event(job_id, {"type": "done", "result": res})
    except Exception as exc:
        with _JOBS_LOCK:
            _JOBS[job_id]["status"] = "error"
            _JOBS[job_id]["error"] = f"{type(exc).__name__}: {exc}"
        _push_job_event(job_id, {"type": "error", "error": f"{type(exc).__name__}: {exc}"})
    finally:
        usage.clear_context()


# ── HTTP Request Handler ──────────────────────────────────────────────────────

def _validate_inspection_payload(body: dict) -> None:
    """Reject unusable jobs before spawning threads or making paid model calls."""
    hive_id = body.get("hive_id", "")
    if not isinstance(hive_id, str) or not _safe_part(hive_id) or not (config.HIVES_DIR / hive_id / "hive.json").is_file():
        raise ValueError("Choose an existing hive before starting an inspection.")
    try:
        date.fromisoformat(body.get("date", ""))
    except (ValueError, TypeError):
        raise ValueError("Choose a valid inspection date.") from None
    days = float(body.get("days_on_board", 3))
    frames = float(body.get("frames_in_hive", 10))
    if not math.isfinite(days) or not 0.5 <= days <= 30:
        raise ValueError("Board duration must be between 0.5 and 30 days.")
    if not math.isfinite(frames) or not frames.is_integer() or not 1 <= frames <= 40:
        raise ValueError("Frames in hive must be a whole number between 1 and 40.")
    photos = body.get("frames_b64") or []
    samples = body.get("frame_samples") or []
    if not isinstance(photos, list) or not isinstance(samples, list):
        raise ValueError("Frame photos and samples must be lists.")
    if len(photos) + len(samples) > 8:
        raise ValueError("Choose up to 8 frame photos per inspection.")
    if not (body.get("board_b64") or body.get("board_sample") or photos or samples):
        raise ValueError("Add at least one sticky-board or frame photo.")
    available = get_samples()
    if body.get("board_sample") and body["board_sample"] not in {b["name"] for b in available["boards"]}:
        raise ValueError("The selected board sample is no longer available.")
    if any(name not in {f["name"] for f in available["frames"]} for name in samples):
        raise ValueError("A selected frame sample is no longer available.")
    if not isinstance(body.get("note", ""), str) or len(body.get("note", "")) > 4000:
        raise ValueError("Keep field notes below 4,000 characters.")
    captures = body.get("capture_sources", {})
    allowed_photos = ({"board"} if body.get("board_b64") else set()) | {f"frame_{i + 1}" for i in range(len(photos))}
    if not isinstance(captures, dict) or not set(captures) <= allowed_photos:
        raise ValueError("Capture sources must refer to uploaded photos.")
    for capture in captures.values():
        if not isinstance(capture, dict) or set(capture) != {"source", "name", "captured_at", "width", "height", "video_seconds"}:
            raise ValueError("Invalid capture source.")
        if capture["source"] not in ("camera", "video", "demo"):
            raise ValueError("Unknown capture source.")
        if not isinstance(capture["name"], str) or len(capture["name"]) > 200:
            raise ValueError("Invalid capture name.")
        try:
            from datetime import datetime
            datetime.fromisoformat(capture["captured_at"].replace("Z", "+00:00"))
        except (ValueError, TypeError, AttributeError):
            raise ValueError("Invalid capture time.") from None
        if any(type(capture[key]) is not int or not 1 <= capture[key] <= 4096 for key in ("width", "height")):
            raise ValueError("Invalid capture dimensions.")
        seconds = capture["video_seconds"]
        if seconds is not None and (type(seconds) not in (int, float) or not math.isfinite(seconds) or seconds < 0):
            raise ValueError("Invalid video position.")


class HiveLensHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args) -> None:
        # Quiet logging so terminal stays clean
        pass

    def _send_json(self, data: object, status: int = 200) -> None:
        body = json.dumps(data, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length > MAX_REQUEST_BYTES:
            self.close_connection = True
            raise ValueError("Upload is too large. Keep photos below 60 MB total.")
        if length <= 0:
            return {}
        body = json.loads(self.rfile.read(length).decode("utf-8"))
        if not isinstance(body, dict):
            raise ValueError("Expected a JSON object")
        return body

    def do_GET(self) -> None:
        parsed = urllib.parse.urlsplit(self.path)
        path = parsed.path
        query = dict(urllib.parse.parse_qsl(parsed.query))

        if path in ("/", "/index.html", "/designs", "/designs/"):
            html = (UI_PATH.with_name("designs.html") if path.rstrip("/") == "/designs" else UI_PATH).read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(html)
            return

        if path.startswith("/static/"):
            # Explicit allowlist: never expose the data directory or local config.
            assets = {"app.css": "text/css; charset=utf-8", "app.js": "text/javascript; charset=utf-8", "mark.svg": "image/svg+xml",
                      "farm.css": "text/css; charset=utf-8", "farm.js": "text/javascript; charset=utf-8",
                      "account.css": "text/css; charset=utf-8", "account.js": "text/javascript; charset=utf-8",
                      "camera.js": "text/javascript; charset=utf-8", "comb-demo.mp4": "video/mp4",
                      "yard.js": "text/javascript; charset=utf-8",
                      "layouts.css": "text/css; charset=utf-8", "layouts.js": "text/javascript; charset=utf-8",
                      "layouts-next.css": "text/css; charset=utf-8", "layouts-next.js": "text/javascript; charset=utf-8",
                      **{f"design-previews/{key}.jpg": "image/jpeg" for key in
                         ("focus", "registry", "panorama", "notebook", "triage", "fieldbook",
                          "board", "atlas", "chronicle", "workbench", "folio", "dispatch")}}
            name = path.removeprefix("/static/")
            # Weather icons (Meteocons, MIT): only plain names inside static/weather/.
            if name.startswith("weather/") and _safe_part(name.removeprefix("weather/")) and name.endswith(".svg") \
                    and (STATIC_DIR / name).is_file():
                assets = {**assets, name: "image/svg+xml"}
            if name not in assets:
                self._send_json({"error": "not found"}, 404)
                return
            content = (STATIC_DIR / name).read_bytes()
            start, end, status = 0, len(content) - 1, 200
            if name == "comb-demo.mp4" and self.headers.get("Range"):
                try:
                    unit, span = self.headers["Range"].split("=", 1)
                    first, last = span.split("-", 1)
                    if unit != "bytes" or "," in span or not (first or last):
                        raise ValueError
                    if first:
                        start = int(first)
                        end = min(int(last), end) if last else end
                    else:
                        suffix = int(last)
                        if suffix <= 0:
                            raise ValueError
                        start = max(0, len(content) - suffix)
                    if start < 0 or start > end:
                        raise ValueError
                    status = 206
                except ValueError:
                    self.send_response(416)
                    self.send_header("Content-Range", f"bytes */{len(content)}")
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
            self.send_response(status)
            self.send_header("Content-Type", assets[name])
            if name == "comb-demo.mp4":
                self.send_header("Accept-Ranges", "bytes")
                if status == 206:
                    self.send_header("Content-Range", f"bytes {start}-{end}/{len(content)}")
            self.send_header("Content-Length", str(end - start + 1))
            self.send_header("Cache-Control", "no-cache")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(content[start:end + 1])
            return

        if path == "/api/settings":
            self._send_json({"settings": settings.load(), "api": self._api_info()})
            return

        if path == "/api/profile_photo":
            photo = settings.photo_path()
            if not photo.exists():
                self._send_json({"error": "No profile photo."}, 404)
                return
            data = photo.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(data)
            return

        if path == "/api/usage":
            s = settings.load()
            data = usage.summary(s["prices"], len(store.list_hives()), s["planning"]["inspections_per_hive_month"])
            self._send_json({**data, "budget": s["planning"]["monthly_budget"]})
            return

        if path == "/api/state":
            eval_path = config.DATA_DIR / "eval" / "varroa_eval.json"
            bench = json.loads(eval_path.read_text()) if eval_path.exists() else None
            demo_dir = config.DATA_DIR / "demo_assets"
            demo_numbers = json.loads((demo_dir / "numbers.json").read_text()) if (demo_dir / "numbers.json").exists() else None
            demo_images = sorted(p.name for p in demo_dir.glob("*.jpg")) if demo_dir.exists() else []
            samples = get_samples()
            self._send_json({
                "version": __version__,
                "has_api_key": config.has_api_key(),
                "profile": settings.load()["profile"],
                "segment_model": config.SEGMENT_MODEL,
                "reasoning_model": config.REASONING_MODEL,
                "thresholds": {
                    "mites_per_day_moderate": config.THRESHOLDS.mites_per_day_moderate,
                    "mites_per_day_high": config.THRESHOLDS.mites_per_day_high,
                    "stores_weeks_low": config.THRESHOLDS.stores_weeks_low,
                    "stores_weeks_ok": config.THRESHOLDS.stores_weeks_ok,
                },
                "class_colors": CLASS_COLORS,
                "class_labels": CLASS_LABELS,
                "hives": store.list_hives(),
                "farms": store.list_farms(),
                "apiary": build_apiary_overview(),
                "samples": {
                    "boards": [{"name": b["name"], "experts": b["experts"]} for b in samples["boards"]],
                    "frames": [{"name": f["name"]} for f in samples["frames"]],
                },
                "benchmark": bench,
                "demo_assets": {"numbers": demo_numbers, "images": demo_images},
            })
            return

        if path.startswith("/api/weather/"):
            farm = store.get_farm(urllib.parse.unquote(path.removeprefix("/api/weather/")))
            if farm is None:
                self._send_json({"error": "Unknown farm."}, 404)
                return
            if farm.get("lat") is None or farm.get("lon") is None:
                self._send_json({"error": "Add a location or a Google Maps link to this farm to see its weather."}, 409)
                return
            try:
                data = place.forecast(farm["lat"], farm["lon"])
            except Exception:
                self._send_json({"error": "The weather service did not answer. Try again in a minute."}, 502)
                return
            self._send_json({"farm_id": farm["id"], **data})
            return

        if path.startswith("/api/demo_asset/"):
            name = urllib.parse.unquote(path.removeprefix("/api/demo_asset/"))
            demo_dir = config.DATA_DIR / "demo_assets"
            fpath = demo_dir / name
            if not _safe_part(name) or not _inside(fpath, demo_dir) or fpath.suffix.lower() not in (".jpg", ".jpeg", ".png", ".webp"):
                self._send_json({"error": "not allowed"}, 403)
                return
            if not fpath.exists():
                self._send_json({"error": "not found"}, 404)
                return
            self._serve_image(fpath, int(query.get("max_side", "0")))
            return

        if path.startswith("/api/hive/"):
            hive_id = urllib.parse.unquote(path.removeprefix("/api/hive/"))
            if not _safe_part(hive_id):
                self._send_json({"error": "bad hive id"}, 400)
                return
            insps = store.inspections(hive_id)
            rows = store.metrics_rows(hive_id)
            self._send_json({"hive_id": hive_id, "inspections": insps, "metrics_rows": rows})
            return

        if path.startswith("/api/file/"):
            # /api/file/<hive_id>/<insp_id>/<filename>?max_side=1400
            parts = [urllib.parse.unquote(p) for p in path.removeprefix("/api/file/").split("/") if p]
            if len(parts) != 3 or not all(_safe_part(p) for p in parts):
                self._send_json({"error": "bad file path"}, 400)
                return
            fpath = store.file_path(parts[0], parts[1], parts[2])
            if not _inside(fpath, config.HIVES_DIR) or fpath.suffix.lower() not in (".jpg", ".jpeg", ".png", ".webp"):
                self._send_json({"error": "not allowed"}, 403)
                return
            if not fpath.exists():
                self._send_json({"error": "not found"}, 404)
                return
            self._serve_image(fpath, int(query.get("max_side", "0")))
            return

        if path.startswith("/api/sample_preview/"):
            # /api/sample_preview/board/<name> or /api/sample_preview/frame/<name>
            parts = [urllib.parse.unquote(p) for p in path.removeprefix("/api/sample_preview/").split("/") if p]
            if len(parts) != 2:
                self._send_json({"error": "bad preview path"}, 400)
                return
            kind, name = parts
            samples = get_samples()
            items = samples["boards"] if kind == "board" else samples["frames"]
            match = next((x for x in items if x["name"] == name), None)
            if not match or not Path(match["path"]).exists():
                self._send_json({"error": "sample not found"}, 404)
                return
            self._serve_image(Path(match["path"]), int(query.get("max_side", "900")))
            return

        if path.startswith("/api/export/"):
            hive_id = urllib.parse.unquote(path.removeprefix("/api/export/").removesuffix(".zip"))
            if not _safe_part(hive_id) or not (config.HIVES_DIR / hive_id / "hive.json").exists():
                self._send_json({"error": "unknown hive"}, 404)
                return
            data = store.export_zip(hive_id)
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Disposition", f'attachment; filename="hivelens_{hive_id}.zip"')
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return

        if path.startswith("/api/jobs/") and path.endswith("/stream"):
            job_id = path.removeprefix("/api/jobs/").removesuffix("/stream")
            self._stream_job(job_id)
            return

        self._send_json({"error": "not found"}, 404)

    @staticmethod
    def _api_info() -> dict:
        """What the settings page may show about the connection. Never the key itself."""
        return {"has_api_key": config.has_api_key(), "base_url": config.API_BASE,
                "segment_model": config.SEGMENT_MODEL, "reasoning_model": config.REASONING_MODEL,
                "reasoning_effort": config.REASONING_EFFORT}

    def _serve_image(self, fpath: Path, max_side: int = 0) -> None:
        cache_key = f"{fpath}:{fpath.stat().st_mtime_ns}:{max_side}"
        if cache_key in _THUMB_CACHE:
            data = _THUMB_CACHE[cache_key]
        else:
            if max_side > 0:
                img = open_image_path(fpath)
                w, h = img.size
                if max(w, h) > max_side:
                    scale = max_side / max(w, h)
                    img = img.resize((max(1, round(w * scale)), max(1, round(h * scale))), Image.LANCZOS)
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=86)
                data = buf.getvalue()
            else:
                data = fpath.read_bytes()
            if len(_THUMB_CACHE) < 128:
                _THUMB_CACHE[cache_key] = data

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "image/jpeg")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "public, max-age=3600")
        self.end_headers()
        self.wfile.write(data)

    def _stream_job(self, job_id: str) -> None:
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")  # no Content-Length: the stream ends when the socket closes
        self.end_headers()

        try:
            cursor = max(0, int(self.headers.get("Last-Event-ID", "0")))
        except ValueError:
            cursor = 0
        heartbeat = time.monotonic()
        while True:
            with _JOBS_LOCK:
                job = _JOBS.get(job_id)
                if not job:
                    payload = json.dumps({"type": "error", "error": "Unknown job"})
                    self.wfile.write(f"data: {payload}\n\n".encode("utf-8"))
                    self.wfile.flush()
                    return
                cursor = min(cursor, len(job["events"]))
                start_cursor = cursor
                events = job["events"][cursor:]
                cursor = len(job["events"])
                status = job["status"]

            try:
                for event_id, ev in enumerate(events, start_cursor + 1):
                    data = json.dumps(ev, default=str)
                    self.wfile.write(f"id: {event_id}\ndata: {data}\n\n".encode("utf-8"))
                    self.wfile.flush()
                if time.monotonic() - heartbeat >= 15:
                    self.wfile.write(b": heartbeat\n\n")
                    self.wfile.flush()
                    heartbeat = time.monotonic()
            except (BrokenPipeError, ConnectionResetError):
                return  # Closing a tab must not stop the background inspection.

            if status in ("done", "error") and not events:
                return
            time.sleep(0.12)

    def do_POST(self) -> None:
        parsed = urllib.parse.urlsplit(self.path)
        path = parsed.path
        try:
            body = self._read_json()
        except Exception as e:
            self._send_json({"error": f"Invalid JSON: {e}"}, 400)
            return

        if path == "/api/profile_photo":
            # {"image": "data:image/...;base64,..."} to upload, {"remove": true} to go back to the default
            try:
                if body.get("remove"):
                    saved = settings.set_photo(None)
                else:
                    raw = base64.b64decode(str(body.get("image", "")).split(",", 1)[-1], validate=True)
                    if not raw or len(raw) > 8_000_000:
                        raise ValueError("Choose a photo under 8 MB.")
                    saved = settings.set_photo(open_image_bytes(raw))
            except Exception as exc:
                msg = str(exc) if isinstance(exc, ValueError) and "photo" in str(exc) else "That file is not a photo HiveLens can read. Use JPEG, PNG or WebP."
                self._send_json({"error": msg}, 400)
                return
            self._send_json({"settings": saved})
            return

        if path == "/api/settings":
            try:
                saved = settings.save(body)
            except ValueError as exc:
                self._send_json({"error": str(exc)}, 400)
                return
            self._send_json({"settings": saved, "api": self._api_info()})
            return

        if path in ("/api/farms", "/api/farm_update"):
            try:
                fields = farm_fields(body)
            except ValueError as exc:
                self._send_json({"error": str(exc)}, 400)
                return
            if path == "/api/farm_update":
                farm_id = str(body.get("farm_id", ""))
                if store.get_farm(farm_id) is None:
                    self._send_json({"error": "Unknown farm."}, 404)
                    return
            fields, warning = locate_farm(fields)
            if path == "/api/farms":
                f = store.create_farm(fields["name"], fields["location"])
                farm_id = f["id"]
            f = store.update_farm(farm_id, **{k: (v if v != "" else None) for k, v in fields.items() if k != "name"}, name=fields["name"])
            self._send_json({"farm": f, "warning": warning, "farms": store.list_farms(), "apiary": build_apiary_overview()})
            return

        if path == "/api/hives":
            name = str(body.get("name", "")).strip()
            loc = str(body.get("location", "")).strip()
            farm_id = body.get("farm_id") or None
            if not name:
                self._send_json({"error": "Hive name is required"}, 400)
                return
            if farm_id is not None and (not isinstance(farm_id, str) or store.get_farm(farm_id) is None):
                self._send_json({"error": "Choose an existing farm."}, 400)
                return
            h = store.create_hive(name, loc, farm_id)
            self._send_json({"hive": h, "hives": store.list_hives(), "apiary": build_apiary_overview()})
            return

        if path == "/api/hive_layout":
            # {"farm_id": ..., "positions": [{"hive_id", "x_m", "y_m"}]} or {"farm_id": ..., "reset": true}
            farm_id = body.get("farm_id") or None
            members = {h["id"] for h in store.list_hives() if (h.get("farm_id") or None) == farm_id}
            try:
                if body.get("reset"):
                    for hive_id in members:
                        store.update_hive(hive_id, x_m=None, y_m=None)
                else:
                    positions = body.get("positions")
                    if not isinstance(positions, list) or not positions or len(positions) > 500:
                        raise ValueError("Send the hive positions to save.")
                    for p in positions:
                        if not isinstance(p, dict) or p.get("hive_id") not in members:
                            raise ValueError("Every hive must belong to this farm.")
                        x, y = float(p["x_m"]), float(p["y_m"])
                        if not (math.isfinite(x) and math.isfinite(y)):
                            raise ValueError("Positions must be numbers.")
                    for p in positions:
                        store.update_hive(p["hive_id"], x_m=float(p["x_m"]), y_m=float(p["y_m"]))
            except (ValueError, TypeError, KeyError) as exc:
                self._send_json({"error": str(exc) or "Invalid positions."}, 400)
                return
            self._send_json({"hives": store.list_hives(), "apiary": build_apiary_overview()})
            return

        if path == "/api/hive_style":
            hive_id = str(body.get("hive_id", ""))
            if not _safe_part(hive_id) or not (config.HIVES_DIR / hive_id / "hive.json").exists():
                self._send_json({"error": "Unknown hive."}, 404)
                return
            try:
                h = store.update_hive(hive_id, color=body.get("color") or None)
            except ValueError as exc:
                self._send_json({"error": str(exc)}, 400)
                return
            self._send_json({"hive": h, "hives": store.list_hives(), "apiary": build_apiary_overview()})
            return

        if path == "/api/hive_farm":
            hive_id = str(body.get("hive_id", ""))
            farm_id = body.get("farm_id") or None
            if not _safe_part(hive_id) or not (config.HIVES_DIR / hive_id / "hive.json").exists():
                self._send_json({"error": "Unknown hive."}, 404)
                return
            if farm_id is not None and (not isinstance(farm_id, str) or store.get_farm(farm_id) is None):
                self._send_json({"error": "Choose an existing farm."}, 400)
                return
            h = store.set_hive_farm(hive_id, farm_id)
            self._send_json({"hive": h, "hives": store.list_hives(), "apiary": build_apiary_overview()})
            return

        if path == "/api/seed_apiary":
            res = seed_demo_apiary()
            self._send_json({**res, "hives": store.list_hives()})
            return

        if path == "/api/commons":
            titles = body.get("titles") or ([body["title"]] if body.get("title") else commons.DEMO_FRAMES)
            saved = []
            errors = []
            for t in titles:
                try:
                    saved.append(commons.fetch(str(t).strip()))
                except Exception as e:
                    errors.append(str(e))
            samples = get_samples(force=True)
            self._send_json({"saved": saved, "errors": errors, "frames": samples["frames"]})
            return

        if path == "/api/inspect":
            try:
                _validate_inspection_payload(body)
            except (ValueError, TypeError) as exc:
                self._send_json({"error": str(exc)}, 400)
                return
            if not config.has_api_key():
                self._send_json({"error": "No MODEL_API_KEY configured in .env"}, 400)
                return
            job_id = uuid.uuid4().hex[:12]
            with _JOBS_LOCK:
                _JOBS[job_id] = {"status": "running", "progress": 0.0, "message": "Starting inspection…", "events": []}
            t = threading.Thread(target=_run_inspection_job, args=(job_id, body), daemon=True)
            t.start()
            self._send_json({"job_id": job_id})
            return

        if path == "/api/benchmark":
            try:
                n_boards = int(body.get("n_boards", 12))
                skip = int(body.get("skip", 8))
                if not 1 <= n_boards <= 30 or skip < 0:
                    raise ValueError
            except (ValueError, TypeError):
                self._send_json({"error": "Choose 1–30 boards and a non-negative starting offset."}, 400)
                return
            if not config.has_api_key():
                self._send_json({"error": "No MODEL_API_KEY configured in .env"}, 400)
                return
            job_id = uuid.uuid4().hex[:12]
            with _JOBS_LOCK:
                _JOBS[job_id] = {"status": "running", "progress": 0.0, "message": "Starting benchmark…", "events": []}
            t = threading.Thread(target=_run_benchmark_job, args=(job_id, body), daemon=True)
            t.start()
            self._send_json({"job_id": job_id})
            return

        self._send_json({"error": "not found"}, 404)


def main() -> None:
    url = f"http://{HOST}:{PORT}"
    server = ThreadingHTTPServer((HOST, PORT), HiveLensHandler)
    print(f"\n🐝 HiveLens {__version__} is live at:  {url}")
    print(f"   Segmentation : {config.SEGMENT_MODEL}")
    print(f"   Reasoning    : {config.REASONING_MODEL}")
    print("   Press Ctrl+C to stop.\n")
    threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down HiveLens…")
        server.server_close()


if __name__ == "__main__":
    main()
