#!/usr/bin/env python3
"""
Generate a demo HTML from the latest match data.
- Replaces all summoner names with anonymous English placeholders
- Defaults the output HTML to English (EN) mode
- Saves to output/demo.html (not archived)

Usage:
    python src/make_demo.py
    python src/make_demo.py --dir data/  # specify data directory
"""
import argparse
import copy
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).parent))

# Fake summoner names (10 players, 5v5)
FAKE_NAMES = [
    ("SilverArrow",  "NA1"),
    ("DarkMage",     "NA1"),
    ("IronWarden",   "NA1"),
    ("SwiftBlade",   "NA1"),
    ("StormCaller",  "NA1"),
    ("VoidWalker",   "NA1"),
    ("FrostBite",    "NA1"),
    ("ShadowStep",   "NA1"),
    ("BlazeFury",    "NA1"),
    ("TideBreaker",  "NA1"),
]

ap = argparse.ArgumentParser(description="Generate demo HTML with anonymized summoner names")
ap.add_argument("--dir", default=str(ROOT / "data"), help="Data directory (default: data/)")
args = ap.parse_args()

data_dir = Path(args.dir).expanduser().resolve()

# ── load .env for PLATFORM ──────────────────────────────────────────────────
def load_env(path):
    env = {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                env[key.strip()] = val.strip()
    except FileNotFoundError:
        pass
    return env

_env     = load_env(ROOT / ".env")
PLATFORM = _env.get("PLATFORM", "JP1").upper()

MATCH_RE = re.compile(rf"^{re.escape(PLATFORM)}_(\d+)\.json$")
TL_RE    = re.compile(rf"^{re.escape(PLATFORM)}_(\d+)_timeline\.json$")

files = list(data_dir.iterdir())
match_candidates = [p for p in files if MATCH_RE.match(p.name)]
if not match_candidates:
    print(f"❌ No match JSON found in {data_dir}")
    sys.exit(1)

match_path = max(match_candidates, key=lambda p: p.stat().st_mtime)
game_id = MATCH_RE.match(match_path.name).group(1)
timeline_path = data_dir / f"{PLATFORM}_{game_id}_timeline.json"
if not timeline_path.exists():
    print(f"❌ Timeline not found: {timeline_path}")
    sys.exit(1)

print(f"[demo] Using: {match_path.name}")

match_data = json.loads(match_path.read_text(encoding="utf-8"))
timeline_data = json.loads(timeline_path.read_text(encoding="utf-8"))

# ── anonymize match data ──────────────────────────────────────────────────────
DEMO_ID = f"{PLATFORM}_000000000"

match_demo = copy.deepcopy(match_data)
participants = match_demo["info"]["participants"]

USER_PUUID = _env.get("PUUID", "")

# Determine which teamId the real user belongs to (for ally detection)
_real_user_team = next(
    (p.get("teamId", 100) for p in participants if p.get("puuid") == USER_PUUID),
    100  # fallback to team 100
)

for i, p in enumerate(participants):
    name, tag = FAKE_NAMES[i % len(FAKE_NAMES)]
    p["riotIdGameName"] = name
    p["riotIdTagline"]  = tag
    p["summonerName"]   = name
    # PUUIDs are anonymised below — do not leak real PUUIDs into demo HTML
    p["puuid"] = f"DEMO_PUUID_{i}"

# Make ally Jinx the "user" in the demo so the golden highlight is visible.
# Pick the first Jinx on the same team as the real user (fallback: any Jinx).
DEMO_USER_PUUID = "DEMO_USER_PUUID"
_jinx = next(
    (p for p in participants
     if p.get("championName") == "Jinx" and p.get("teamId") == _real_user_team),
    next((p for p in participants if p.get("championName") == "Jinx"), None)
)
if _jinx:
    _jinx["puuid"] = DEMO_USER_PUUID

# Replace identifying metadata
match_demo["metadata"]["matchId"]  = DEMO_ID
match_demo["info"]["gameDuration"] = 1380   # 23:00
match_demo["info"]["gameVersion"]  = "16.4.0.0"  # keeps ddragon version (16.4.1) intact

# ── write to temp dir and generate HTML ──────────────────────────────────────
with tempfile.TemporaryDirectory() as tmpdir:
    tmp = Path(tmpdir)
    demo_match     = tmp / f"{DEMO_ID}.json"
    demo_timeline  = tmp / f"{DEMO_ID}_timeline.json"
    demo_match.write_text(json.dumps(match_demo, ensure_ascii=False), encoding="utf-8")
    demo_timeline.write_text(timeline_data if isinstance(timeline_data, str)
                             else json.dumps(timeline_data, ensure_ascii=False),
                             encoding="utf-8")

    # Run viewer (suppressing organize_all_outputs to avoid archiving current output)
    import lol_html_viewer_auto
    lol_html_viewer_auto.USER_PUUID = DEMO_USER_PUUID  # ally Jinx as the demo user
    sys.argv = ["lol_html_viewer_auto.py", "--dir", str(tmp), "--no-csv", "--lang", "en"]

    # Capture the output file path by monkey-patching OUTPUT_DIR temporarily
    import io, contextlib
    from datetime import datetime
    out_buf = io.StringIO()
    with contextlib.redirect_stdout(out_buf):
        lol_html_viewer_auto.main()
    output_log = out_buf.getvalue()
    print(output_log, end="")

# Find the generated file (most recently modified html in output/)
output_dir = ROOT / "output"
html_files = sorted(output_dir.glob("out_*.html"), key=lambda p: p.stat().st_mtime, reverse=True)
if not html_files:
    print("❌ Could not find generated HTML")
    sys.exit(1)

latest_html = html_files[0]

# ── patch: set English as default language ───────────────────────────────────
content = latest_html.read_text(encoding="utf-8")
content = content.replace("let currentLang = 'ja';", "let currentLang = 'en';", 1)
# Add applyLang call after renderAll is wired up
content = content.replace(
    "requestAnimationFrame(renderAll);",
    "requestAnimationFrame(() => { renderAll(); applyLang('en'); });",
    1
)

demo_out = output_dir / "demo.html"
demo_out.write_text(content, encoding="utf-8")

# Remove the temp-named html (keep only demo.html)
if latest_html != demo_out:
    latest_html.unlink()

print(f"\n[demo] Saved: {demo_out}")
print("   Open in browser -- all summoner names are anonymized, UI defaults to English.")
