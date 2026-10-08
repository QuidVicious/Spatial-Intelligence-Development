"""
Domain Lab: run the real domain engine on a saved run, outside the pipeline.

It imports domain_engine itself, so the model, temperature, thinking budget, camera
telemetry and prompt are exactly what a fresh capture would use. The one thing you can
change is the system instruction, read from a text file. Nothing in the pipeline changes.

Commands (run from the project folder, beside server.py):

  python domain_lab.py dump
      Writes the engine's current system instruction to lab/instruction_current.md.
      Copy it, edit the copy, and pass the copy to "run" or "studio".

  python domain_lab.py run --run RUN_ID [--instruction FILE] [--repeat N] [--label NAME]
      Runs the domain analysis on that run's archived capture. Without --instruction it
      uses the engine's current instruction (your baseline). Results go to
      lab/RUN_ID/<time>_<label>/ : one .md per repeat, compare.md, and the instruction used.

  python domain_lab.py studio --run RUN_ID [--instruction FILE]
      Writes the exact system instruction, user prompt and settings for AI Studio, plus a
      copy of the capture to attach. No API call is made.

A/B testing: run the baseline and the variant with the same --repeat (3 is a good start).
The engine varies a little between calls even at temperature 0, so compare variant runs
against baseline runs made the same day, not against the run's archived original.
"""

import argparse
import base64
import difflib
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from dotenv import load_dotenv

ENV_PATH = Path(r"C:\DEV\Squid\SquidBlack\.env")
if ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH)
else:
    load_dotenv()

import domain_engine
from domain_engine import ViewScope, analyze_spatial_domain

try:
    from archiver import DEFAULT_RUNS_DIR
except Exception:
    DEFAULT_RUNS_DIR = Path("runs")

LAB_DIR = Path("lab")

SECTIONS = [
    ("Centroid", lambda r: (r.metadata or {}).get("centroid", "")),
    ("Geology", lambda r: r.geological_foundation),
    ("Architecture", lambda r: r.architectural_analysis),
    ("Materials", lambda r: r.material_and_lithics),
    ("Condition", lambda r: r.surface_condition),
    ("Ecology", lambda r: r.botanical_ecology),
    ("Decluttering", lambda r: r.static_decluttering_summary),
    ("Documentary prompt", lambda r: r.documentary_prompt),
]


# ---------------------------------------------------------------- loading a run

def load_run(run_id: str, runs_dir: Path) -> dict:
    d = runs_dir / run_id
    if not d.is_dir():
        sys.exit(f"Run not found: {d}")
    capture = d / "viewport_capture.jpg"
    if not capture.exists():
        sys.exit(f"{run_id} has no viewport_capture.jpg to analyse.")
    meta = json.loads((d / "run_metadata.json").read_text(encoding="utf-8"))
    dom_path = d / "domain_result.json"
    dom = json.loads(dom_path.read_text(encoding="utf-8")) if dom_path.exists() else {}
    dmeta = dom.get("metadata") or {}
    tel = dict(meta.get("telemetry") or {})
    if not tel:
        sys.exit(f"{run_id} has no telemetry in run_metadata.json.")

    coords = dmeta.get("coordinates")
    if coords and len(coords) == 2:
        subject = (float(coords[0]), float(coords[1]))
    elif tel.get("target_latitude") is not None:
        subject = (float(tel["target_latitude"]), float(tel["target_longitude"]))
    else:
        subject = (float(tel["latitude"]), float(tel["longitude"]))

    scope_raw = str(dom.get("view_scope") or "FRUSTUM").split(".")[-1].upper()
    scope = ViewScope(scope_raw) if scope_raw in ViewScope.__members__ else ViewScope.FRUSTUM
    b64 = base64.b64encode(capture.read_bytes()).decode("ascii")
    return {
        "dir": d,
        "capture_path": capture,
        "address": dom.get("address") or dmeta.get("address") or "Unknown address",
        "subject": subject,
        "scope": scope,
        "telemetry": SimpleNamespace(**tel),
        "date": tel.get("date"),
        "grounding": bool(dmeta.get("search_grounding")),
        "screenshot_b64": f"data:image/jpeg;base64,{b64}",
        "original": dom,
    }


def call_engine(run: dict, api_key=None):
    return analyze_spatial_domain(
        address=run["address"],
        coordinates=run["subject"],
        view_scope=run["scope"],
        telemetry=run["telemetry"],
        screenshot_b64=run["screenshot_b64"],
        temporal_epoch=run["date"],
        gemini_api_key=api_key or os.getenv("GEMINI_API_KEY"),
        use_search_grounding=run["grounding"],
    )


def use_instruction(path):
    """Swap the engine's system instruction for the file's text. Returns the text in use."""
    if path:
        text = Path(path).read_text(encoding="utf-8")
        domain_engine.DOMAIN_SYSTEM_INSTRUCTION = text
        return text
    return domain_engine.DOMAIN_SYSTEM_INSTRUCTION


# ---------------------------------------------------------------- formatting

def sections_md(result, title: str) -> str:
    out = [f"# {title}\n"]
    for name, get in SECTIONS:
        body = (get(result) or "").strip() or "_(empty)_"
        out.append(f"## {name}\n{body}\n")
    return "\n".join(out)


def word_diff(a: str, b: str) -> str:
    """Words removed from a shown as [-like this-], words added in b as {+like this+}."""
    aw, bw = a.split(), b.split()
    out = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, aw, bw).get_opcodes():
        if op == "equal":
            out.extend(aw[i1:i2])
        if op in ("delete", "replace"):
            out.append("[-" + " ".join(aw[i1:i2]) + "-]")
        if op in ("insert", "replace"):
            out.append("{+" + " ".join(bw[j1:j2]) + "+}")
    return " ".join(out)


# ---------------------------------------------------------------- commands

def cmd_dump(_args):
    LAB_DIR.mkdir(exist_ok=True)
    p = LAB_DIR / "instruction_current.md"
    p.write_text(domain_engine.DOMAIN_SYSTEM_INSTRUCTION, encoding="utf-8")
    print(f"Wrote {p} ({len(domain_engine.DOMAIN_SYSTEM_INSTRUCTION)} chars). Copy it and edit the copy.")


def cmd_run(args):
    run = load_run(args.run, Path(args.runs_dir))
    instruction = use_instruction(args.instruction)
    label = args.label or (Path(args.instruction).stem if args.instruction else "baseline")
    out = LAB_DIR / args.run / f"{datetime.now():%Y%m%d_%H%M%S}_{re.sub(r'[^A-Za-z0-9_-]', '_', label)}"
    out.mkdir(parents=True, exist_ok=True)
    (out / "instruction_used.md").write_text(instruction, encoding="utf-8")

    print(f"[Lab] {args.run} | {label} | model {domain_engine.DOMAIN_MODEL} | {args.repeat} repeat(s)")
    prompts = []
    for i in range(1, args.repeat + 1):
        result = call_engine(run)
        (out / f"repeat_{i}.md").write_text(sections_md(result, f"{label}, repeat {i}"), encoding="utf-8")
        (out / f"repeat_{i}.json").write_text(json.dumps(result.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
        prompts.append(result.documentary_prompt)
        print(f"  repeat {i}: documentary prompt {len(result.documentary_prompt)} chars")

    original = (run["original"].get("documentary_prompt") or "").strip()
    lines = [f"# Compare: {label} on {args.run}\n",
             f"Instruction: {args.instruction or 'engine current (baseline)'}  ",
             f"Model: {domain_engine.DOMAIN_MODEL}  ",
             f"Lengths: {', '.join(str(len(p)) for p in prompts)} chars"
             + (f" (archived original: {len(original)})" if original else "") + "\n"]
    for i, p in enumerate(prompts, 1):
        lines.append(f"## Repeat {i}\n{p}\n")
        if i > 1:
            lines.append(f"### Changes from repeat 1\n{word_diff(prompts[0], p)}\n")
    if original:
        lines.append("## Archived original (made with the instruction of its day)\n" + original + "\n")
        lines.append("### Changes from the archived original to repeat 1\n" + word_diff(original, prompts[0]) + "\n")
    (out / "compare.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"[Lab] Done. Open {out / 'compare.md'}")


def cmd_studio(args):
    run = load_run(args.run, Path(args.runs_dir))
    instruction = use_instruction(args.instruction)
    captured = {}

    class _Models:
        def generate_content(self, model, contents, config):
            captured.update(model=model, contents=contents, config=config)
            return SimpleNamespace(text="")

    class _Client:
        def __init__(self, *a, **k):
            self.models = _Models()

    real_genai = domain_engine.genai
    domain_engine.genai = SimpleNamespace(Client=_Client)
    try:
        call_engine(run, api_key="studio-export")   # builds the exact request; nothing is sent
    finally:
        domain_engine.genai = real_genai

    texts = [c for c in captured["contents"] if isinstance(c, str)]
    has_image = len(captured["contents"]) > len(texts)
    cfg = captured["config"]
    budget = getattr(getattr(cfg, "thinking_config", None), "thinking_budget", None)
    out = LAB_DIR / args.run
    out.mkdir(parents=True, exist_ok=True)
    stamp = f"{datetime.now():%Y%m%d_%H%M%S}"
    image_copy = out / f"studio_{stamp}_capture.jpg"
    image_copy.write_bytes(run["capture_path"].read_bytes())
    doc = f"""# AI Studio version: {args.run}

Made {stamp} from {args.instruction or 'the engine current instruction'}. Nothing was sent to the API.

## Settings
- Model: {captured['model']}
- Temperature: {cfg.temperature}
- Top P: {cfg.top_p}
- Thinking budget: {budget}
- Google Search grounding: {'ON' if getattr(cfg, 'tools', None) else 'OFF'}

## Steps
1. Paste the system instruction below into System Instructions.
2. {'Attach ' + image_copy.name + ' FIRST (the engine sends the image before the text), then paste the user prompt below in the same message.' if has_image else 'Paste the user prompt below (this run sends no image).'}
3. Run. The output uses the same labelled sections as the pipeline.

AI Studio matches the engine closely but not exactly: the engine's calls also vary slightly
between runs, so judge by several runs, not one.

## System instruction
````text
{cfg.system_instruction}
````

## User prompt
````text
{chr(10).join(texts)}
````
"""
    p = out / f"studio_{stamp}.md"
    p.write_text(doc, encoding="utf-8")
    print(f"[Lab] Wrote {p} and {image_copy.name}")


def main():
    ap = argparse.ArgumentParser(description="Run the real domain engine on a saved run.")
    ap.add_argument("--runs-dir", default=str(DEFAULT_RUNS_DIR), help="Archived runs folder")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("dump", help="Write the engine's current instruction to lab/")
    for name in ("run", "studio"):
        s = sub.add_parser(name)
        s.add_argument("--run", required=True, help="Run folder name, e.g. 4_Ainslie_Pl_..._20261002_160630")
        s.add_argument("--instruction", help="Edited instruction file; omit for the engine's current one")
        if name == "run":
            s.add_argument("--repeat", type=int, default=1, help="Calls to make (3 shows the variation)")
            s.add_argument("--label", help="Name for this test; defaults to the instruction file name")
    args = ap.parse_args()
    {"dump": cmd_dump, "run": cmd_run, "studio": cmd_studio}[args.cmd](args)


if __name__ == "__main__":
    main()
