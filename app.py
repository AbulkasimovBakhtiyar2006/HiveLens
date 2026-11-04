"""HiveLens UI. Run with:  streamlit run app.py"""

from __future__ import annotations

import json
import sys
from datetime import date

import pandas as pd
import streamlit as st
from PIL import Image, ImageOps

from hivelens import __version__, config, store
from hivelens.viz import CLASS_COLORS, CLASS_LABELS

Image.MAX_IMAGE_PIXELS = None  # sticky-board photos are ~49 MP

st.set_page_config(page_title="HiveLens", page_icon="🐝", layout="wide")

LEVEL_BADGE = {"good": "🟢 good", "watch": "🟡 watch", "act": "🔴 act", "unknown": "⚪ no data"}
VERDICT_ICON = {"verified": "✅", "rejected": "❌", "unverifiable": "❔"}
URGENCY = {"now": "🔴 now", "this_week": "🟠 this week", "next_inspection": "🟢 next inspection"}


def open_image(upload) -> Image.Image:
    return ImageOps.exif_transpose(Image.open(upload)).convert("RGB")


# ── sidebar: hive picker ──────────────────────────────────────────────────────

with st.sidebar:
    st.markdown(f"## 🐝 HiveLens `{__version__}`")
    if config.has_api_key():
        st.success("Meta Model API key loaded")
    else:
        st.error("No MODEL_API_KEY. Copy .env.example to .env and add your key.")
    st.caption(f"Segmentation: `{config.SEGMENT_MODEL}`  \nReasoning: `{config.REASONING_MODEL}`")

    hives = store.list_hives()
    names = {h["id"]: f'{h["name"]}' + (f' · {h["location"]}' if h.get("location") else "") for h in hives}
    hive_id = st.selectbox("Hive", list(names), format_func=names.get) if hives else None

    with st.expander("➕ New hive", expanded=not hives):
        with st.form("new_hive", clear_on_submit=True):
            n = st.text_input("Name", placeholder="Hive #1")
            loc = st.text_input("Apiary / location", placeholder="Talgar apiary")
            if st.form_submit_button("Create") and n.strip():
                h = store.create_hive(n.strip(), loc.strip())
                st.success(f"Created {h['name']}")
                st.rerun()

st.title("HiveLens")
st.caption("Photograph a frame and the sticky board. SAM 3.1 measures, Muse Spark reasons, and every claim is checked against the numbers.")

if not hive_id:
    st.info("Create a hive in the sidebar to start.")
    st.stop()


# ── one inspection ────────────────────────────────────────────────────────────

def show_inspection(rec: dict, ctx: str = "view") -> None:
    status = rec.get("status", {})
    levels = status.get("levels", {})
    st.markdown(
        f"### {rec['date']} · overall {LEVEL_BADGE.get(status.get('overall', 'unknown'))}  \n"
        + " · ".join(f"**{k}** {LEVEL_BADGE.get(v)}" for k, v in levels.items())
    )
    for f in status.get("flags", []):
        st.warning(f)

    m = rec.get("metrics", {})
    cols = st.columns(5)
    cards = [
        ("Mites / day", m.get("mites_per_day"), m.get("mites_per_day_change")),
        ("Mites counted", m.get("mite_count"), None),
        ("Capped honey, %", m.get("honey_pct"), None),
        ("Brood, %", m.get("brood_total_pct"), m.get("brood_total_pct_change")),
        ("Stores, weeks", m.get("stores_weeks"), None),
    ]
    for col, (label, val, delta) in zip(cols, cards):
        col.metric(label, "—" if val is None else val, delta=None if delta is None else delta, delta_color="inverse" if "Mites" in label else "normal")

    report = rec.get("report")
    left, right = st.columns([3, 2])
    with left:
        files = rec.get("files", {})
        for key in [k for k in files if k.endswith("_overlay")]:
            pid = key.removesuffix("_overlay")
            cap = "SAM 3.1 mites + Muse Spark votes" if pid == "board" else "SAM 3.1 comb outline & bees + Muse Spark tile labels"
            st.image(str(store.file_path(hive_id, rec["id"], files[key])), caption=f"{pid}: {cap}")
        if any(k.startswith("frame") for k in files):
            st.markdown(" ".join(
                f"<span style='background:rgb{CLASS_COLORS[k]};padding:2px 8px;border-radius:6px;"
                f"color:{'#000' if k in ('honey', 'larvae', 'empty') else '#fff'}'>{CLASS_LABELS[k]}</span>"
                for k in CLASS_COLORS), unsafe_allow_html=True)
        if "board" in files:
            st.caption("Board: 🟢 mite found by SAM 3.1 · 🔵 mite found by the Muse Spark vote · ❌ candidate rejected by the size/colour checks")

    with right:
        if report:
            st.markdown("#### Muse Spark report")
            st.write(report.get("summary", ""))
            for f in report.get("findings", []):
                st.markdown(f"✅ {f['text']}  `{', '.join(f.get('claim_ids', []))}`")
            if report.get("actions"):
                st.markdown("**What to do**")
                for a in report["actions"]:
                    st.markdown(f"- {URGENCY.get(a.get('urgency'), a.get('urgency'))}: **{a['action']}** — {a.get('reason', '')}")
            for c in report.get("caveats", []):
                st.caption(f"⚠️ {c}")
            if report.get("discarded_findings"):
                with st.expander(f"🗑 {len(report['discarded_findings'])} finding(s) dropped: no verified evidence"):
                    for f in report["discarded_findings"]:
                        st.markdown(f"- ~~{f['text']}~~")
        else:
            st.info("Measured without the agent.")

        claims = rec.get("claims", [])
        if claims:
            st.markdown("#### Hypotheses vs measurements")
            for c in claims:
                icon = VERDICT_ICON.get(c.get("verdict"), "•")
                st.markdown(f"{icon} `{c.get('id')}` {c.get('statement', '')}  \n"
                            f"<small>{c.get('metric')} {c.get('op')} {c.get('value')} → {c.get('reason', '')}</small>",
                            unsafe_allow_html=True)

    with st.expander("Agent trace (every tool call)"):
        for e in rec.get("trace", []):
            if e["type"] == "thought":
                st.markdown(f"💭 {e['text']}")
            elif e["type"] == "tool_call":
                st.markdown(f"🔧 `{e['name']}` {json.dumps(e.get('args', {}))[:300]}")
            elif e["type"] == "tool_result":
                st.code(json.dumps(e.get("result"), indent=1)[:1500], language="json")
            elif e["type"] == "claim":
                st.markdown(f"{VERDICT_ICON.get(e.get('verdict'))} claim `{e.get('id')}`: {e.get('statement')} — {e.get('reason')}")
    st.download_button("Download inspection JSON", json.dumps(rec, indent=2, default=str),
                       file_name=f"{hive_id}_{rec['id']}.json", mime="application/json", key=f"dl_{ctx}_{rec['id']}")


tab_new, tab_hist, tab_bench, tab_about = st.tabs(["🔍 New inspection", "📈 Hive history", "📊 Benchmark", "ℹ️ How it works"])

with tab_new:
    c1, c2 = st.columns(2)
    with c1:
        frames_up = st.file_uploader("Frame photos (one side of a frame per photo)", type=["jpg", "jpeg", "png", "webp"], accept_multiple_files=True)
        board_up = st.file_uploader("Sticky board photo (varroa drop)", type=["jpg", "jpeg", "png", "webp"])
        with st.expander("🖼 Add a frame photo from Wikimedia Commons"):
            st.caption("Openly licensed photos only; author and licence are saved to data/demo/comb/CREDITS.json.")
            title = st.text_input("Commons file name", placeholder="File:A slice of the brood nest.jpg")
            cc1, cc2 = st.columns(2)
            if cc1.button("Download", disabled=not title.strip()):
                from hivelens import commons

                try:
                    c = commons.fetch(title.strip())
                    st.success(f"Saved {c['file']} · {c['author']} · {c['license']}")
                except Exception as e:
                    st.error(str(e))
            if cc2.button("Download the 3 demo frames"):
                from hivelens import commons

                for t in commons.DEMO_FRAMES:
                    try:
                        c = commons.fetch(t)
                        st.success(f"Saved {c['file']} · {c['author']} · {c['license']}")
                    except Exception as e:
                        st.error(str(e))
        sample_boards = sorted((config.DATA_DIR / "varroa").rglob("images/*.jpg"))
        sample_frames = sorted(p for p in (config.DATA_DIR / "demo" / "comb").glob("*")
                               if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"))
        board_pick = frames_pick = None
        if sample_boards or sample_frames:
            with st.expander("…or use sample photos", expanded=not (frames_up or board_up)):
                if sample_boards:
                    name = st.selectbox("Sample sticky board (public dataset)", ["—"] + [p.name for p in sample_boards])
                    board_pick = next((p for p in sample_boards if p.name == name), None)
                    if board_pick:
                        xml = next(board_pick.parent.parent.rglob(board_pick.stem + ".xml"), None)
                        if xml:
                            st.caption(f"Experts counted {xml.read_text().count('<object>')} mites on this board.")
                if sample_frames:
                    names = st.multiselect("Sample frame photos", [p.name for p in sample_frames])
                    frames_pick = [p for p in sample_frames if p.name in names]
    with c2:
        insp_date = st.date_input("Inspection date", value=date.today())
        days = st.number_input("Days the board was in the hive", 0.5, 30.0, 3.0, 0.5)
        frames_in_hive = st.number_input("Frames in the hive", 1, 40, 10)
        detail = st.selectbox("Board reading", ["thorough (600 px grid + re-check of dark spots)", "fast (600 px grid only)"],
                              help="The re-check sends up to 250 extra 300 px crops around dark spots SAM did not explain.")
        note = st.text_area("Note for the agent (optional)", placeholder="Colony seemed defensive, saw a few bees with deformed wings")
        use_agent = st.checkbox("Run the Muse Spark agent", value=True)

    if st.button("Run inspection", type="primary", disabled=not (frames_up or board_up or board_pick or frames_pick)):
        if not config.has_api_key():
            st.error("Add MODEL_API_KEY to .env first.")
            st.stop()
        frames = [open_image(f) for f in (frames_up or [])] + [open_image(p) for p in (frames_pick or [])]
        board = open_image(board_up) if board_up else (open_image(board_pick) if board_pick else None)
        bar = st.progress(0.0, "Starting")
        live = st.status("Agent at work", expanded=True) if use_agent else None

        def on_event(e):
            if not live:
                return
            if e["type"] == "claim":
                live.write(f"{VERDICT_ICON.get(e['verdict'])} {e.get('statement')} — {e.get('reason')}")
            elif e["type"] == "tool_call" and e["name"] != "check_claim":
                live.write(f"🔧 {e['name']} {json.dumps(e.get('args', {}))[:120]}")

        try:
            from hivelens.pipeline import run_inspection

            rec = run_inspection(
                hive_id, insp_date.isoformat(), frames=frames, board=board, days_on_board=days,
                frames_in_hive=int(frames_in_hive), note=note, use_agent=use_agent,
                board_refine=detail.startswith("thorough"),
                progress=lambda msg, frac: bar.progress(min(frac, 1.0), msg), on_event=on_event,
            )
        except Exception as e:
            st.exception(e)
            st.stop()
        bar.progress(1.0, "Done")
        if live:
            live.update(label="Agent finished", state="complete", expanded=False)
        show_inspection(rec, "new")

with tab_hist:
    items = store.inspections(hive_id)
    if not items:
        st.info("No inspections yet for this hive.")
    else:
        df = pd.DataFrame(store.metrics_rows(hive_id)).set_index("date")
        series = [c for c in ("mites_per_day", "honey_kg_hive_est", "brood_total_pct", "stores_weeks") if c in df]
        if series:
            cols = st.columns(len(series))
            for col, s in zip(cols, series):
                col.markdown(f"**{s}**")
                col.line_chart(df[[s]])
        st.dataframe(df, width="stretch")
        if st.button("📦 Prepare export (ZIP: photos, overlays, reports, metrics.csv)"):
            st.session_state[f"zip_{hive_id}"] = store.export_zip(hive_id)
        if st.session_state.get(f"zip_{hive_id}"):
            st.download_button("⬇️ Download ZIP", st.session_state[f"zip_{hive_id}"],
                               file_name=f"hivelens_{hive_id}.zip", mime="application/zip")
        pick = st.selectbox("Open inspection", [i["id"] for i in reversed(items)])
        show_inspection(next(i for i in items if i["id"] == pick), "history")

with tab_bench:
    path = config.DATA_DIR / "eval" / "varroa_eval.json"
    have_data = any((config.DATA_DIR / "varroa").rglob("*.xml")) if (config.DATA_DIR / "varroa").exists() else False
    if not have_data:
        st.info("Run `python scripts/download_varroa.py` to get the expert-annotated boards, then come back here.")
    else:
        with st.expander("▶ Run the benchmark", expanded=not path.exists()):
            b1, b2, b3 = st.columns(3)
            n_boards = b1.number_input("Boards", 1, 40, 12)
            skip = b2.number_input("Skip first (development boards)", 0, 20, 8)
            use_muse = b3.checkbox("Muse Spark vote", value=True)
            if st.button("Run benchmark", disabled=not config.has_api_key()):
                import importlib.util

                spec = importlib.util.spec_from_file_location("eval_varroa", config.ROOT / "scripts" / "eval_varroa.py")
                ev_mod = importlib.util.module_from_spec(spec)
                sys.path.insert(0, str(config.ROOT / "scripts"))
                spec.loader.exec_module(ev_mod)
                bar = st.progress(0.0, "Starting")
                log_box = st.empty()
                lines: list[str] = []

                def log(msg):
                    lines.append(str(msg))
                    log_box.code("\n".join(lines[-12:]))

                ev_mod.evaluate(int(n_boards), int(skip), muse=use_muse, log=log,
                                progress=lambda done, total: bar.progress(min(done / total, 1.0), f"board {min(int(done) + 1, total)}/{total}"))
                bar.progress(1.0, "Done")
                st.rerun()

    if path.exists():
        ev = json.loads(path.read_text())
        s = ev["summary"]
        c = st.columns(5)
        c[0].metric("Boards (held out)", s["images"])
        c[1].metric("HiveLens precision", s.get("sam_precision"))
        c[2].metric("HiveLens recall", s.get("sam_recall"))
        c[3].metric("Count error, mites/board", s["sam_mae"], help="mean absolute error vs experts")
        c[4].metric("Classic CV count error", s["cv_mae"])
        rows = pd.DataFrame(ev["images"]).set_index("image")
        rows = rows.rename(columns={"sam": "hivelens"})
        st.bar_chart(rows[["experts", "hivelens"]])
        st.dataframe(rows, width="stretch")
        st.caption(ev.get("note", ""))

with tab_about:
    st.markdown("""
**Pipeline**
1. **SAM 3.1** (Meta) segments open-vocabulary concepts: `varroa mite` on the sticky board (tiled at full resolution),
   and `honeycomb` + `honey bee` on frame photos; Muse Spark then labels a grid of comb tiles
   (capped honey / capped brood / open brood / pollen / empty), because SAM treats those as one big region.
2. **Deterministic engine** (plain Python) turns masks into numbers: mite count and mites/day after size and shape
   checks, comb composition in % of visible comb, honey estimate in kg, weeks of stores, trends against earlier inspections.
3. **Rules** set the traffic light (good / watch / act). The model cannot change it.
4. **Muse Spark** (Meta) looks at the photos and must first commit to visual hypotheses. Each one is checked against
   the measurements and comes back verified or rejected. Only findings backed by verified claims reach the report.
5. Each hive keeps its history; everything exports as a ZIP with a metrics CSV.

Thresholds are defaults in `hivelens/config.py`; tune them for your region and season.
""")
