"""The HiveLens inspection agent, driven by Muse Spark with tool calling.

Flow the agent is forced into:
  1. Look at the photos and state visual hypotheses as checkable claims
     (`check_claim`). Measurements stay hidden until it has committed to two.
  2. Read the SAM-based measurements and the hive's history.
  3. Optionally ask SAM 3.1 for extra concepts (queen cells, drone brood, ...).
  4. Submit a report. Every finding must cite claims the engine verified;
     findings without a verified claim are dropped before the report is saved.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Callable

from PIL import Image

from . import config, engine, measure
from .meta_client import client as default_client
from .meta_client import data_url

SYSTEM_PROMPT = """You are HiveLens, an inspection agent for beekeepers.
You receive photos from one hive inspection: frame sides (comb) and/or a sticky board
from under the hive that collects fallen varroa mites.

Rules you must follow:
- Measurements come from SAM 3.1 masks and plain arithmetic. They are hidden until you
  have recorded at least two visual hypotheses with `check_claim`. Make those hypotheses
  from what you see, e.g. {"metric": "honey_pct", "op": "about", "value": 40}.
- A claim is checked against the measurements and comes back verified, rejected or
  unverifiable. If a hypothesis is rejected, say so plainly and correct yourself.
- The overall status (good / watch / act) is decided by rules in `get_measurements`.
  You explain it; you never contradict it.
- Every finding in `submit_report` must cite the ids of verified claims. Unsupported
  findings are discarded.
- Be concrete and practical. No medical or veterinary diagnosis: describe what is
  measured and suggest what a beekeeper would check or do next.
- Finish by calling `submit_report` exactly once."""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "check_claim",
            "description": "Check one quantitative statement against the measurements. Returns verdict and the measured value.",
            "parameters": {
                "type": "object",
                "properties": {
                    "statement": {"type": "string", "description": "The claim in plain words."},
                    "metric": {"type": "string", "description": "Measurement key, e.g. honey_pct, brood_total_pct, mites_per_day, mite_count, stores_weeks, pollen_pct, bees_pct, empty_pct, honey_kg_hive_est, mites_per_day_change."},
                    "op": {"type": "string", "enum": list(engine.OPS)},
                    "value": {"type": "number"},
                    "value_max": {"type": "number", "description": "Upper bound, only for op=between."},
                },
                "required": ["statement", "metric", "op", "value"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_measurements",
            "description": "Returns all measured metrics for this inspection plus rule-based status levels. Available after two claims were checked.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_history",
            "description": "Returns metrics from earlier inspections of the same hive, oldest first.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "segment",
            "description": "Run SAM 3.1 on one photo with a free text concept (e.g. 'queen cell', 'drone brood cells', 'wax moth larva'). Returns count and area. Max 3 calls.",
            "parameters": {
                "type": "object",
                "properties": {
                    "photo": {"type": "string", "description": "Photo id from the list you were given."},
                    "concept": {"type": "string"},
                },
                "required": ["photo", "concept"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "submit_report",
            "description": "Submit the final inspection report.",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string", "description": "2-3 sentences for the beekeeper."},
                    "findings": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "text": {"type": "string"},
                                "claim_ids": {"type": "array", "items": {"type": "string"}},
                            },
                            "required": ["text", "claim_ids"],
                        },
                    },
                    "actions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "action": {"type": "string"},
                                "urgency": {"type": "string", "enum": ["now", "this_week", "next_inspection"]},
                                "reason": {"type": "string"},
                            },
                            "required": ["action", "urgency", "reason"],
                        },
                    },
                    "caveats": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["summary", "findings", "actions"],
            },
        },
    },
]


@dataclass
class AgentRun:
    report: dict | None = None
    claims: list[dict] = field(default_factory=list)
    trace: list[dict] = field(default_factory=list)
    usage_tokens: int = 0

    def to_json(self) -> dict:
        return {"report": self.report, "claims": self.claims, "trace": self.trace, "usage_tokens": self.usage_tokens}


def _jsonable(x):
    return json.loads(json.dumps(x, default=str))


def run_agent(
    photos: dict[str, Image.Image],
    metrics: dict,
    history: list[dict],
    *,
    note: str = "",
    llm=None,
    max_steps: int = 14,
    on_event: Callable[[dict], None] | None = None,
) -> AgentRun:
    llm = llm or default_client()
    run = AgentRun()
    status = engine.assess(metrics)
    segment_calls = 0

    def emit(event: dict):
        run.trace.append(_jsonable(event))
        if on_event:
            on_event(event)

    def tool(name: str, args: dict):
        nonlocal segment_calls
        if name == "check_claim":
            verdict = engine.verify_claim(args, metrics)
            verdict["id"] = f"c{len(run.claims) + 1}"
            run.claims.append(_jsonable(verdict))
            emit({"type": "claim", **verdict})
            return verdict
        if name == "get_measurements":
            if len(run.claims) < 2:
                return {"error": "Record at least two visual hypotheses with check_claim first."}
            return {"metrics": metrics, "status": status}
        if name == "get_history":
            return {"inspections": history} if history else {"inspections": [], "note": "first inspection of this hive"}
        if name == "segment":
            if segment_calls >= 3:
                return {"error": "segment limit reached"}
            img = photos.get(args.get("photo", ""))
            if img is None:
                return {"error": f"unknown photo, use one of {list(photos)}"}
            segment_calls += 1
            return measure.extra_concept(img, str(args.get("concept", ""))[:80])
        if name == "submit_report":
            return _accept_report(args, run, status)
        return {"error": f"unknown tool {name}"}

    content: list[dict] = [{
        "type": "text",
        "text": (
            f"Inspection photos: {', '.join(photos)}.\n"
            + (f"Beekeeper note: {note}\n" if note else "")
            + "Start with your visual hypotheses."
        ),
    }]
    for pid, img in photos.items():
        content.append({"type": "text", "text": f"Photo `{pid}`:"})
        content.append({"type": "image_url", "image_url": {"url": data_url(img, max_side=1024, quality=85)}})

    messages: list[dict] = [
        {"role": "developer", "content": SYSTEM_PROMPT},
        {"role": "user", "content": content},
    ]

    for step in range(max_steps):
        resp = llm.chat.completions.create(
            model=config.REASONING_MODEL,
            messages=messages,
            tools=TOOLS,
            reasoning_effort=config.REASONING_EFFORT,
            max_completion_tokens=4000,
        )
        if getattr(resp, "usage", None):
            run.usage_tokens += getattr(resp.usage, "total_tokens", 0) or 0
        msg = resp.choices[0].message
        if msg.content:
            emit({"type": "thought", "step": step, "text": msg.content})

        calls = list(msg.tool_calls or [])
        if not calls:
            if run.report:
                break
            messages.append({"role": "assistant", "content": msg.content or ""})
            messages.append({"role": "user", "content": "Please finish by calling submit_report."})
            continue

        messages.append({
            "role": "assistant",
            "content": msg.content or "",
            "tool_calls": [
                {"id": c.id, "type": "function", "function": {"name": c.function.name, "arguments": c.function.arguments or "{}"}}
                for c in calls
            ],
        })
        for c in calls:
            try:
                args = json.loads(c.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            emit({"type": "tool_call", "step": step, "name": c.function.name, "args": args})
            try:
                result = tool(c.function.name, args)
            except Exception as e:  # a failing tool must not kill the run
                result = {"error": f"{type(e).__name__}: {e}"}
            if c.function.name != "check_claim":
                emit({"type": "tool_result", "step": step, "name": c.function.name, "result": result})
            messages.append({"role": "tool", "tool_call_id": c.id, "content": json.dumps(_jsonable(result))})

        if run.report:
            break

    if not run.report:
        run.report = {
            "summary": "The agent did not finish its report; showing measured status only.",
            "status": status, "findings": [], "actions": [], "caveats": ["agent did not complete"],
            "discarded_findings": [],
        }
    return run


def _accept_report(args: dict, run: AgentRun, status: dict) -> dict:
    verified = {c["id"] for c in run.claims if c.get("verdict") == "verified"}
    kept, dropped = [], []
    for f in args.get("findings") or []:
        ids = [i for i in (f.get("claim_ids") or []) if i in verified]
        (kept if ids else dropped).append({**f, "claim_ids": ids or f.get("claim_ids", [])})
    run.report = _jsonable({
        "summary": args.get("summary", ""),
        "status": status,
        "findings": kept,
        "actions": args.get("actions") or [],
        "caveats": args.get("caveats") or [],
        "discarded_findings": dropped,
    })
    return {"accepted": True, "kept_findings": len(kept), "discarded_unverified": len(dropped)}
