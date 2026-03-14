#!/usr/bin/env python3
"""
Fetch the latest champion ID → name mapping from Data Dragon and update
assets/00_champ.json (Japanese names).

Usage:
    python src/update_champs.py           # fetch latest version
    python src/update_champs.py --version 16.5.1
"""
import argparse
import json
import sys
import urllib.request
from pathlib import Path

ROOT       = Path(__file__).resolve().parent.parent
CHAMP_FILE = ROOT / "assets" / "00_champ.json"

VERSIONS_URL = "https://ddragon.leagueoflegends.com/api/versions.json"
CHAMP_URL    = "https://ddragon.leagueoflegends.com/cdn/{version}/data/ja_JP/champion.json"

ap = argparse.ArgumentParser(description="Update assets/00_champ.json from Data Dragon")
ap.add_argument("--version", default=None, help="Data Dragon version (default: latest)")
args = ap.parse_args()

def fetch_json(url: str):
    with urllib.request.urlopen(url, timeout=10) as r:
        return json.loads(r.read().decode("utf-8"))

if args.version:
    version = args.version
else:
    print("Fetching latest Data Dragon version...")
    versions = fetch_json(VERSIONS_URL)
    version = versions[0]

print(f"Version: {version}")
print("Fetching champion data (ja_JP)...")

data   = fetch_json(CHAMP_URL.format(version=version))
champs = data["data"]

# Build {champion_key (numeric str): japanese_name}
champ_map = {}
for _, v in champs.items():
    champ_map[v["key"]] = v["name"]

champ_map_sorted = dict(sorted(champ_map.items(), key=lambda x: int(x[0])))

CHAMP_FILE.write_text(
    json.dumps(champ_map_sorted, ensure_ascii=False, indent=2),
    encoding="utf-8",
)
print(f"Updated: {CHAMP_FILE} ({len(champ_map_sorted)} champions)")
