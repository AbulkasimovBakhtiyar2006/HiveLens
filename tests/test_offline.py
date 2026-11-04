"""Offline tests: no API key needed. SAM output is synthesized with Meta's own codec,
and Muse Spark is replaced by a scripted fake that calls the same tools."""

from __future__ import annotations

import json
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image

from meta_sam_parser._mask_codec import _encode_raster  # noqa: E402

from hivelens import agent, config, engine, measure, sam, store  # noqa: E402


@pytest.fixture(autouse=True)
def isolated_data(tmp_path, monkeypatch):
    # Works even when another test module imported config before this module.
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "HIVES_DIR", tmp_path / "hives")
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path / "cache")


def sam_line(objects: list[tuple[int, int, int, int, float]], w: int, h: int) -> str:
    """Builds a SAM API image line with filled-ellipse masks."""
    recs = []
    for oid, (x1, y1, x2, y2, c) in enumerate(objects):
        mw, mh = x2 - x1, y2 - y1
        yy, xx = np.mgrid[0:mh, 0:mw]
        m = (((xx - mw / 2) / (mw / 2)) ** 2 + ((yy - mh / 2) / (mh / 2)) ** 2 <= 1).astype(int)
        payload = _encode_raster([int(v) for v in m.flatten()], mw, mh)
        recs.append(
            f"{oid}<|box;x1={x1};y1={y1};x2={x2 - 1};y2={y2 - 1};w={w};h={h};c={c}|>"
            f"<|mask;x=0;y=0;c={c};data={mh},{mw},{payload}|>"
        )
    return "<0f>" + ",".join(recs)


def test_parse_roundtrip():
    raw = sam_line([(10, 20, 40, 44, 0.9), (100, 100, 130, 125, 0.8)], 300, 200)
    found = sam.parse_raw(raw, "varroa mite", offset=(1000, 0))
    assert len(found) == 2
    a = found[0]
    assert a.box == (1010, 20, 1040, 44)
    assert a.mask.shape == (24, 30) and 0.6 < a.mask.mean() < 0.9
    assert abs(a.confidence - 0.9) < 1e-6


def test_empty_output():
    assert sam.parse_raw("", "x") == []


def test_mite_filter_rejects_debris():
    good = [sam.Instance("m", (i * 50, 0, i * 50 + 30, 24), 0.9) for i in range(8)]
    big = sam.Instance("m", (0, 100, 200, 260), 0.9)
    thin = sam.Instance("m", (0, 300, 120, 310), 0.9)
    weak = sam.Instance("m", (0, 400, 30, 424), 0.1)
    kept, rejected = measure.filter_mites(good + [big, thin, weak])
    assert len(kept) == 8 and len(rejected) == 3


def test_tiling_and_nms(monkeypatch):
    calls = []

    # 2600 px wide → two tiles: x 0..1344 and 1256..2600. A mite at global x 1280..1310
    # sits in the overlap, so both tiles report it and NMS must keep one copy.
    def fake_raw(img, concept, use_cache=True):
        calls.append(img.size)
        w, h = img.size
        if len(calls) == 1:
            return sam_line([(5, 5, 35, 29, 0.9), (1280, 600, 1310, 624, 0.9)], w, h)
        return sam_line([(24, 600, 54, 624, 0.8), (1000, 5, 1030, 29, 0.9)], w, h)

    monkeypatch.setattr(sam, "raw_segment", fake_raw)
    img = Image.new("RGB", (2600, 1300), "white")
    out = sam.segment(img, "varroa mite", tile=1344, overlap=96, workers=1)
    assert calls == [(1344, 1300), (1344, 1300)]
    assert len(out) == 3
    assert list(sam.tiles(8064, 6048, 1344, 96))[-1][2:] == (8064, 6048)


def test_comb_from_tiles():
    """Bees (SAM masks) hide comb first; every other pixel takes its tile's Muse Spark label."""
    W, H = 400, 200
    found = {
        "comb": [sam.Instance("comb", (0, 0, W, H), 0.9, np.ones((H, W), bool))],
        "bees": [sam.Instance("bees", (0, 0, 100, 100), 0.9, np.ones((100, 100), bool))],
    }
    tiles, _ = measure.comb_grid((W, H), found["comb"], cols=4)  # 4 x 3 tiles of 100 x 66
    assert len(tiles) == 12
    labels = {i: ("H" if i % 4 < 2 else "B") for i in range(12)}  # left half honey, right half brood
    labels[11] = "X"                                               # one unreadable tile
    r = measure.comb_from_tiles((W, H), found, tiles, labels)
    f = r.fractions
    assert round(sum(f.values())) == 100 and r.bee_count == 1
    assert 10 < f["bees"] < 15 and f["brood"] > f["honey"] > 30  # bees hide part of the honey half
    assert r.metrics()["tiles_read"] == 11


def test_engine_rules_and_claims():
    m = engine.aggregate({"mite_count": 42, "days_on_board": 3, "mites_per_day": 14.0, "rejected_detections": 2},
                         [{"honey_pct": 40, "brood_pct": 20, "larvae_pct": 5, "pollen_pct": 5, "empty_pct": 20,
                           "bees_pct": 10, "honey_kg_this_side": 0.6}], 10)
    s = engine.assess(m)
    assert s["levels"]["varroa"] == "act" and s["overall"] == "act"
    assert engine.verify_claim({"metric": "honey_pct", "op": "about", "value": 45}, m)["verdict"] == "verified"
    assert engine.verify_claim({"metric": "honey_pct", "op": ">", "value": 70}, m)["verdict"] == "rejected"
    assert engine.verify_claim({"metric": "nope", "op": ">", "value": 1}, m)["verdict"] == "unverifiable"


class FakeMuse:
    """Plays a fixed script of tool calls, like Muse Spark would."""

    def __init__(self, script):
        self.script = list(script)
        self.seen = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kw):
        self.seen.append(kw["messages"])
        calls = self.script.pop(0)
        tcs = [SimpleNamespace(id=f"t{len(self.seen)}_{i}", function=SimpleNamespace(name=n, arguments=json.dumps(a)))
               for i, (n, a) in enumerate(calls)]
        msg = SimpleNamespace(content="thinking", tool_calls=tcs or None)
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)], usage=SimpleNamespace(total_tokens=10))


def test_agent_flow_keeps_only_verified_findings():
    metrics = {"honey_pct": 40.0, "mites_per_day": 14.0, "brood_total_pct": 25.0, "stores_weeks": 12.0}
    fake = FakeMuse([
        [("get_measurements", {})],  # refused: no hypotheses yet
        [("check_claim", {"statement": "lots of honey", "metric": "honey_pct", "op": ">", "value": 70}),
         ("check_claim", {"statement": "mites high", "metric": "mites_per_day", "op": ">=", "value": 10})],
        [("get_measurements", {}), ("get_history", {})],
        [("submit_report", {
            "summary": "Mites high.",
            "findings": [{"text": "Mite drop is high", "claim_ids": ["c2"]},
                         {"text": "Frame is mostly honey", "claim_ids": ["c1"]}],
            "actions": [{"action": "Plan a varroa treatment", "urgency": "this_week", "reason": "14 mites/day"}],
        })],
    ])
    run = agent.run_agent({"board": Image.new("RGB", (64, 64))}, metrics, [], llm=fake)
    assert [c["verdict"] for c in run.claims] == ["rejected", "verified"]
    assert len(run.report["findings"]) == 1 and run.report["findings"][0]["text"] == "Mite drop is high"
    assert len(run.report["discarded_findings"]) == 1
    assert run.report["status"]["overall"] == "act"
    refused = [e for e in run.trace if e["type"] == "tool_result" and e["name"] == "get_measurements"][0]
    assert "error" in refused["result"]


def test_store_and_export():
    hive = store.create_hive("Test hive #1")
    rec = {"date": "2026-11-01", "metrics": {"mites_per_day": 2.0}, "status": {"overall": "good"}}
    store.save_inspection(hive["id"], rec, {"board": Image.new("RGB", (32, 32))}, {})
    rec2 = {"date": "2026-11-08", "metrics": {"mites_per_day": 5.0}, "status": {"overall": "watch"}}
    store.save_inspection(hive["id"], rec2, {}, {})
    assert [h["date"] for h in store.history_before(hive["id"], "2026-11-08")] == ["2026-11-01"]
    data = store.export_zip(hive["id"])
    import io
    import zipfile
    names = zipfile.ZipFile(io.BytesIO(data)).namelist()
    assert any(n.endswith("metrics.csv") for n in names) and any(n.endswith("board.jpg") for n in names)


@pytest.mark.parametrize("capture_source", ["camera", "demo"])
def test_pipeline_end_to_end(monkeypatch, capture_source):
    """Full inspection with fake SAM + fake Muse Spark: measurements, overlays, agent, storage."""
    from hivelens import pipeline

    def fake_raw(img, concept, use_cache=True):
        w, h = img.size
        if concept == measure.MITE_CONCEPT:
            return sam_line([(40 + 60 * i, 50, 70 + 60 * i, 74, 0.9) for i in range(6)], w, h)
        boxes = {
            "honeycomb": [(0, 0, w, h, 0.95)],
            "honey bee": [(10, 10, 60, 40, 0.9)],
        }.get(concept, [])
        return sam_line(boxes, w, h)

    monkeypatch.setattr(sam, "raw_segment", fake_raw)
    monkeypatch.setattr(measure, "mite_body", lambda arr, c: {"area_frac": 4e-5, "redness": 25.0, "aspect": 1.3, "fill": 0.97})
    fake = FakeMuse([
        [("check_claim", {"statement": "mostly honey", "metric": "honey_pct", "op": "about", "value": 50}),
         ("check_claim", {"statement": "few mites", "metric": "mites_per_day", "op": "<", "value": 1})],
        [("get_measurements", {}), ("segment", {"photo": "frame_1", "concept": "queen cell"})],
        [("submit_report", {"summary": "ok", "findings": [{"text": "half the comb is capped honey", "claim_ids": ["c1"]}],
                            "actions": [{"action": "Recheck board", "urgency": "this_week", "reason": "mite drop"}]})],
    ])
    monkeypatch.setattr(agent, "default_client", lambda: fake)
    from hivelens import vote
    # Muse Spark tile labels: left half of the comb honey, right half brood
    monkeypatch.setattr(vote, "label_tiles", lambda frame, rects: {
        i: ("H" if (r[0] + r[2]) / 2 < frame.size[0] / 2 else "B") for i, r in enumerate(rects)})
    hive = store.create_hive("Pipeline hive")
    board = Image.new("RGB", (1500, 1000), "white")
    frame = Image.new("RGB", (800, 500), (200, 160, 60))
    captures = {"frame_1": {"source": capture_source, "name": "Test camera", "captured_at": "2026-11-04T16:00:00Z",
                            "width": 800, "height": 500, "video_seconds": None}}
    rec = pipeline.run_inspection(hive["id"], "2026-11-04", frames=[frame], board=board, days_on_board=2, frames_in_hive=8,
                                board_tile=1344, capture_sources=captures)
    assert rec["inputs"]["capture_sources"]["frame_1"]["source"] == capture_source
    saved = store.inspections(hive["id"])[-1]
    assert saved["inputs"]["capture_sources"] == rec["inputs"]["capture_sources"]
    assert bool(saved.get("demo_capture")) == (capture_source == "demo")
    if capture_source == "demo":
        assert saved["inputs"]["capture_sources"]["frame_1"]["license_url"].endswith("/by-sa/3.0/")
    m = rec["metrics"]
    assert m["mite_count"] == 12 and m["mites_per_day"] == 6.0  # 2 tiles x 6 mites, no overlap duplicates
    assert 35 < m["honey_pct"] < 50  # ellipse masks and m["frames_in_hive"] == 8
    assert rec["status"]["levels"]["varroa"] == "watch"
    assert [c["verdict"] for c in rec["claims"]] == ["verified", "rejected"]
    assert rec["report"]["findings"][0]["claim_ids"] == ["c1"]
    assert {"board_overlay", "frame_1_overlay", "board", "frame_1", "board_evidence"} <= set(rec["files"])


def test_varroa_refine_pass_finds_missed_mite(monkeypatch):
    """Grid pass misses the mite; the 300 px re-check around the dark blob finds it."""
    from PIL import ImageDraw

    board = Image.new("RGB", (1200, 900), (225, 228, 240))
    d = ImageDraw.Draw(board)
    d.ellipse((702, 401, 712, 409), fill=(80, 35, 30))  # reddish-brown mite body, mite-sized for a 1200 px photo
    d.ellipse((300, 300, 310, 308), fill=(30, 45, 40))  # greenish-black debris of the same size

    def fake_raw(img, concept, use_cache=True):
        w, h = img.size
        if (w, h) == (measure.REFINE_CROP, measure.REFINE_CROP):
            # the window is centred on the blob, so the mite sits mid-crop
            return sam_line([(w // 2 - 15, h // 2 - 12, w // 2 + 15, h // 2 + 12, 0.7)], w, h)
        return ""  # grid crops: SAM sees nothing (mite too small)

    monkeypatch.setattr(sam, "raw_segment", fake_raw)
    res = measure.measure_varroa(board, 2)
    assert res.count == 1 and res.mites_per_day == 0.5
    assert any("reddish" in why for _, why in res.rejected)  # SAM's hit on the debris is rejected
    cx, cy = res.kept[0].center
    assert abs(cx - 707) < 6 and abs(cy - 405) < 6


def test_muse_vote_contact_sheet(monkeypatch):
    """Muse Spark votes on numbered cut-outs; only voted spots that look like a mite are counted."""
    from PIL import ImageDraw

    from hivelens import vote

    board = Image.new("RGB", (1200, 900), (225, 228, 240))
    d = ImageDraw.Draw(board)
    d.ellipse((702, 401, 712, 409), fill=(80, 35, 30))   # mite
    d.ellipse((300, 300, 310, 308), fill=(30, 45, 40))   # debris
    d.ellipse((900, 600, 910, 608), fill=(85, 38, 32))   # mite the model will not vote for

    monkeypatch.setattr(sam, "raw_segment", lambda img, concept, use_cache=True: "")  # SAM sees nothing
    seen = {}

    def fake_ask(sheet):
        seen["size"] = sheet.size
        return [1, 2]  # votes for the two darkest spots: the debris and the first mite

    monkeypatch.setattr(vote, "_ask", fake_ask)
    res = measure.measure_varroa(board, 1)  # no pre-check: Muse sees the debris too
    assert seen["size"] == (vote.COLS * vote.TILE, vote.TILE)  # one row of three cut-outs
    assert res.count == 1 and res.kept[0].concept == measure.MUSE_CONCEPT
    assert any("reddish" in why for _, why in res.rejected)  # Muse voted for the debris, the engine refused it


def test_gate_shows_muse_only_plausible_spots(monkeypatch):
    """Spots that fail the physical checks never reach Muse Spark; a greyish mite core that
    max(RGB) misses is still proposed, because it is dark in green and blue."""
    from PIL import ImageDraw

    from hivelens import vote

    board = Image.new("RGB", (1200, 900), (225, 228, 240))
    d = ImageDraw.Draw(board)
    d.ellipse((702, 401, 712, 409), fill=(80, 35, 30))    # mite
    d.ellipse((300, 300, 310, 308), fill=(30, 45, 40))    # greenish-black debris
    d.ellipse((900, 600, 910, 608), fill=(100, 70, 62))   # greyish mite core: max(RGB)=100 > threshold 90
    monkeypatch.setattr(sam, "raw_segment", lambda img, concept, use_cache=True: "")
    assert not any(abs((b[0] + b[2]) / 2 - 905) < 6 for b in measure.classic_cv_mites(board))
    seen = {}

    def fake_ask(sheet):
        seen["size"] = sheet.size
        return [1, 2]

    monkeypatch.setattr(vote, "_ask", fake_ask)
    res = measure.measure_varroa(board, 1, gate=True)
    assert len(res.vote_centers) == 2  # debris gated out before the vote
    assert all(abs(cx - 305) > 20 for cx, _ in res.vote_centers)
    assert res.count == 2 and not res.rejected
    assert any(abs(i.center[0] - 905) < 6 for i in res.kept)


def test_shape_checks_reject_rods_and_crumbs():
    """A smooth reddish oval passes; a reddish rod and a ragged reddish crumb of the same size do not."""
    from PIL import ImageDraw

    board = Image.new("RGB", (3000, 2000), (225, 228, 240))
    d = ImageDraw.Draw(board)
    d.ellipse((500, 500, 528, 520), fill=(85, 40, 32))                      # mite-like oval
    d.rectangle((1000, 500, 1050, 515), fill=(85, 40, 32))                  # rod
    d.polygon([(1500, 500), (1530, 505), (1512, 512), (1535, 528), (1505, 522), (1495, 535), (1490, 510)],
              fill=(85, 40, 32))                                            # ragged crumb
    arr = np.asarray(board)
    oval, rod, crumb = (measure.mite_body(arr, c) for c in [(514, 510), (1025, 507), (1510, 515)])
    assert oval["aspect"] < measure.MITE_MAX_ASPECT and oval["fill"] > measure.MITE_MIN_FILL
    assert rod["aspect"] > measure.MITE_MAX_ASPECT
    assert crumb["fill"] < measure.MITE_MIN_FILL


def test_evidence_and_muse_sheets(monkeypatch):
    """The evidence images redraw what the engine decided: Muse's own sheet with its votes and the vetoes."""
    from PIL import ImageDraw

    from hivelens import viz, vote

    board = Image.new("RGB", (1200, 900), (225, 228, 240))
    d = ImageDraw.Draw(board)
    d.ellipse((702, 401, 712, 409), fill=(80, 35, 30))   # mite
    d.ellipse((300, 300, 310, 308), fill=(30, 45, 40))   # debris (darkest, so tile 1)
    d.ellipse((900, 600, 910, 608), fill=(85, 38, 32))   # mite Muse does not vote for
    monkeypatch.setattr(sam, "raw_segment", lambda img, concept, use_cache=True: "")
    monkeypatch.setattr(vote, "_ask", lambda sheet: [1, 2])
    res = measure.measure_varroa(board, 1)
    assert len(res.vote_centers) == 3 and res.vote_yes == [0, 1]

    sheets = viz.muse_sheets(board, res, scale=2)
    assert len(sheets) == 1
    t, top = vote.TILE * 2, 70
    px = sheets[0].getpixel
    assert px((4, top + t // 2)) == viz.RED            # tile 1: Muse said mite, the checks vetoed it
    assert px((t + 4, top + t // 2)) == viz.BLUE       # tile 2: Muse said mite, counted
    assert px((2 * t + 4, top + t // 2)) != viz.BLUE   # tile 3: Muse said no

    ev = viz.evidence_sheet(board, res, cols=4)
    assert ev.size[0] == 8 + 4 * (224 + 8)
    body = measure.mite_body(np.asarray(board), res.kept[0].center)
    assert body["ellipse"] is not None and abs(body["ellipse"][0][0] - 707) < 3
