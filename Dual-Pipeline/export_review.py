"""
export_review.py: small, clearly named copies of renders for uploading to chat.

Each copy is resized (1600 px wide by default, a few hundred KB) and named from
its run record, so the file name itself says what it is:

    20260927_133034_2026-06-21_1200_OVERCAST_seed12345_print.jpg

Usage, from the Dual-Pipeline folder:
    python export_review.py                      the last 4 runs
    python export_review.py --last 9             the last 9 runs
    python export_review.py --series <series id> every frame of a series, in order
    python export_review.py --runs <folder> <folder> ...
Options:
    --width 1600    maximum width in pixels
    --quality 82    JPEG quality
    --raw           also export the raw render (before the canopy composite), where one exists
    --mask          also export the canopy mask, where one exists

Copies go to review_out\\<date_time>\\ with an index.txt mapping each file to its
run folder. Originals are never touched. On Windows the folder opens when done.
"""

import argparse
import datetime
import json
import os
import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    sys.exit("Pillow is needed for this script: pip install pillow")

BASE = Path(__file__).resolve().parent
RUNS = BASE / "spatial_twin_runs"
SERIES = BASE / "spatial_twin_series"
OUT = BASE / "review_out"


def read_json(p: Path) -> dict:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def clock(t) -> str:
    if not isinstance(t, (int, float)):
        return "live"
    h = int(t)
    m = int(round((t - h) * 60))
    if m == 60:
        h, m = h + 1, 0
    return f"{h:02d}{m:02d}"


def label(run_dir: Path) -> str:
    s = read_json(run_dir / "run_metadata.json").get("settings") or {}
    if s.get("series_frame"):
        kind = f"frame{int(s['series_frame']):02d}"
    elif s.get("keystone_print_of"):
        kind = "print"
    elif s.get("keystone_candidate"):
        kind = "keystone"
    elif s.get("replay_of"):
        kind = "replay"
    else:
        kind = "fresh"
    seed = s.get("seed")
    parts = [
        run_dir.name[-15:],                      # when the run was made (YYYYMMDD_HHMMSS)
        s.get("date") or "live",                 # scene date
        clock(s.get("time_of_day")),             # scene time
        (s.get("weather_mode") or "").upper() or "NOWEATHER",
        f"seed{seed}" if seed is not None else "seedNA",
        kind,
    ]
    return "_".join(str(p) for p in parts)


def pick_runs(args) -> list:
    if args.series:
        m = read_json(SERIES / args.series / "manifest.json")
        if not m:
            sys.exit(f"No manifest found for series {args.series}")
        ids = [f.get("run_id") for f in m.get("frames", []) if f.get("run_id")]
        return [RUNS / i for i in ids]
    if args.runs:
        return [RUNS / r for r in args.runs]
    dirs = [d for d in RUNS.iterdir() if d.is_dir() and (d / "spatial_twin.png").exists()]
    dirs.sort(key=lambda d: d.name[-15:])       # folder names end in the run's timestamp
    return dirs[-args.last:]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--last", type=int, default=4)
    ap.add_argument("--series")
    ap.add_argument("--runs", nargs="+")
    ap.add_argument("--width", type=int, default=1600)
    ap.add_argument("--quality", type=int, default=82)
    ap.add_argument("--raw", action="store_true", help="also export spatial_twin_raw.png where present")
    ap.add_argument("--mask", action="store_true", help="also export canopy_mask.png where present")
    args = ap.parse_args()

    runs = pick_runs(args)
    if not runs:
        sys.exit("No runs with a rendered image were found.")
    dest = OUT / datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    dest.mkdir(parents=True, exist_ok=True)

    lines = []
    for n, d in enumerate(runs, 1):
        if not (d / "spatial_twin.png").exists():
            print(f"  skipped (no image): {d.name}")
            continue
        variants = [("spatial_twin.png", "", "RGB")]
        if args.raw:
            variants.append(("spatial_twin_raw.png", "_RAW", "RGB"))
        if args.mask:
            variants.append(("canopy_mask.png", "_MASK", "L"))
        for fname, suffix, mode in variants:
            src = d / fname
            if not src.exists():
                continue
            img = Image.open(src).convert(mode)
            if img.width > args.width:
                img = img.resize((args.width, round(img.height * args.width / img.width)), Image.LANCZOS)
            name = f"{n:02d}_{label(d)}{suffix}.jpg"
            img.save(dest / name, "JPEG", quality=args.quality, optimize=True)
            kb = (dest / name).stat().st_size // 1024
            lines.append(f"{name}  <-  {d.name}/{fname}  ({kb} KB)")
            print(f"  {name}  ({kb} KB)")

    (dest / "index.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\n{len(lines)} file(s) in {dest}")
    if os.name == "nt":
        os.startfile(dest)


if __name__ == "__main__":
    main()
