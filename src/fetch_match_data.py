# pylint: disable=C0103,C0413,R0801,W0621
import argparse
import json
import os
import shutil
import sys
from pathlib import Path

import requests

# --- プロジェクトルートと各ディレクトリ ---
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
ARCHIVE_DIR = DATA_DIR / "archive"


# --- .env パーサー ---
def load_env(path):
    env = {}
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            env[key.strip()] = val.strip()
    return env


PLATFORM_TO_REGION = {
    "BR1": "americas",
    "LA1": "americas",
    "LA2": "americas",
    "NA1": "americas",
    "EUN1": "europe",
    "EUW1": "europe",
    "TR1": "europe",
    "RU": "europe",
    "JP1": "asia",
    "KR": "asia",
    "OC1": "sea",
    "PH2": "sea",
    "SG2": "sea",
    "TH2": "sea",
    "TW2": "sea",
    "VN2": "sea",
}

QUEUE_PRESETS = {
    "swift": 1700,
    "ranked-solo": 420,
    "ranked-flex": 440,
    "normal-draft": 400,
    "normal-blind": 430,
    "aram": 450,
}

# --- CLI 引数 ---
parser = argparse.ArgumentParser(
    description="Fetch latest LoL match and generate HTML viewer"
)
parser.add_argument(
    "--queue",
    "-q",
    default="swift",
    help=(
        "Queue to fetch. Named presets: swift (1700), ranked-solo (420), "
        "ranked-flex (440), normal-draft (400), normal-blind (430), aram (450). "
        "Or pass a numeric queue ID directly. Default: swift"
    ),
)
args = parser.parse_args()

if args.queue.lstrip("-").isdigit():
    QUEUE_ID = int(args.queue)
elif args.queue in QUEUE_PRESETS:
    QUEUE_ID = QUEUE_PRESETS[args.queue]
else:
    print(
        f"❌ Unknown queue '{args.queue}'. Available: {', '.join(QUEUE_PRESETS)} or a numeric ID"
    )
    sys.exit()

# --- .env 読み込み ---
_env = load_env(ROOT / ".env")
API_KEY = _env.get("API_KEY", "")
PLATFORM = _env.get("PLATFORM", "JP1").upper()
PUUID = _env.get("PUUID", "")
REGION = PLATFORM_TO_REGION.get(PLATFORM, "asia")
LANG = _env.get("LANG", "ja").lower()


def t(ja, en):
    """Return ja or en string based on LANG setting."""
    return ja if LANG == "ja" else en


if not API_KEY:
    raise RuntimeError(
        t(
            "❌ API_KEY が .env に見つかりません — KEY=VALUE 形式で設定してください",
            "❌ API_KEY not found in .env — set it in KEY=VALUE format",
        )
    )
if not PUUID:
    raise RuntimeError(
        t(
            "❌ PUUID が .env に見つかりません — PUUID=your-puuid-here を追記してください",
            "❌ PUUID not found in .env — add PUUID=your-puuid-here",
        )
    )
if PLATFORM not in PLATFORM_TO_REGION:
    print(
        t(
            f"[WARN] 不明な PLATFORM '{PLATFORM}' — asia にフォールバックします",
            f"[WARN] Unknown PLATFORM '{PLATFORM}' — falling back to asia",
        )
    )

HEADERS = {"X-Riot-Token": API_KEY}

print(
    t(
        f"🎮 対象キュー: {args.queue} (queue={QUEUE_ID})",
        f"🎮 Queue: {args.queue} (queue={QUEUE_ID})",
    )
)

# --- ディレクトリ準備 ---
os.makedirs(ARCHIVE_DIR, exist_ok=True)


def backup_if_exists(filename):
    path = DATA_DIR / filename
    if path.exists():
        shutil.move(str(path), str(ARCHIVE_DIR / filename))
        print(
            t(
                f"📦 既存ファイル {filename} を data/archive/ に移動しました",
                f"📦 Moved existing {filename} to data/archive/",
            )
        )


# --- 最新のマッチID 1件取得 ---
ids_url = f"https://{REGION}.api.riotgames.com/lol/match/v5/matches/by-puuid/{PUUID}/ids?start=0&count=5&queue={QUEUE_ID}"  # noqa: E501
ids_res = requests.get(ids_url, headers=HEADERS, timeout=30)

if ids_res.status_code == 401:
    print(
        t(
            "❌ 401: APIキーの期限切れです。Riot Developer Portal でキーを再発行し、.env を更新してください\n   https://developer.riotgames.com/",
            "❌ 401: API key expired. Regenerate it at https://developer.riotgames.com/ and update .env",
        )
    )
    sys.exit()
elif ids_res.status_code == 403:
    print(
        t(
            "❌ 403: APIキーが無効です。.env の内容を確認してください",
            "❌ 403: Invalid API key. Check the value in .env",
        )
    )
    sys.exit()
elif ids_res.status_code == 429:
    print(
        t(
            "❌ 429: レート制限中です。少し待ってから再実行してください",
            "❌ 429: Rate limited. Wait a moment and try again",
        )
    )
    sys.exit()
elif ids_res.status_code != 200:
    print(
        t(
            f"❌ マッチID取得失敗：{ids_res.status_code} {ids_res.text}",
            f"❌ Failed to fetch match IDs: {ids_res.status_code} {ids_res.text}",
        )
    )
    sys.exit()

match_ids = ids_res.json()
if not match_ids:
    print(
        t(
            "❌ マッチIDが取得できませんでした",
            "❌ No match IDs returned",
        )
    )
    sys.exit()

match_id = match_ids[0]
print(
    t(
        f"✅ 最新のマッチID：{match_id}",
        f"✅ Latest match ID: {match_id}",
    )
)

# --- 試合詳細取得 ---
match_url = f"https://{REGION}.api.riotgames.com/lol/match/v5/matches/{match_id}"
match_res = requests.get(match_url, headers=HEADERS, timeout=30)

if match_res.status_code == 200:
    filename = f"{match_id}.json"
    backup_if_exists(filename)
    with open(DATA_DIR / filename, "w", encoding="utf-8") as f:
        json.dump(match_res.json(), f, ensure_ascii=False, indent=2)
    print(t(f"📄 {filename} 保存完了！", f"📄 Saved {filename}"))
else:
    print(
        t(
            f"❌ {match_id} 詳細取得失敗：{match_res.status_code} {match_res.text}",
            f"❌ Failed to fetch match detail: {match_res.status_code} {match_res.text}",
        )
    )
    sys.exit()

# --- タイムライン取得 ---
timeline_url = (
    f"https://{REGION}.api.riotgames.com/lol/match/v5/matches/{match_id}/timeline"
)
timeline_res = requests.get(timeline_url, headers=HEADERS, timeout=30)

if timeline_res.status_code == 200:
    timeline_filename = f"{match_id}_timeline.json"
    backup_if_exists(timeline_filename)
    with open(DATA_DIR / timeline_filename, "w", encoding="utf-8") as f:
        json.dump(timeline_res.json(), f, ensure_ascii=False, indent=2)
    print(t(f"⏱️ {timeline_filename} 保存完了！", f"⏱️ Saved {timeline_filename}"))
else:
    print(
        t(
            f"❌ {match_id} タイムライン取得失敗：{timeline_res.status_code} {timeline_res.text}",
            f"❌ Failed to fetch timeline: {timeline_res.status_code} {timeline_res.text}",
        )
    )
    sys.exit()

# --- HTML + CSV 生成 ---
print(t("\n📊 HTMLビューワーを生成します...", "\n📊 Generating HTML viewer..."))
sys.path.insert(0, str(Path(__file__).parent))
import lol_html_viewer_auto  # noqa: E402

sys.argv = ["lol_html_viewer_auto.py"]
lol_html_viewer_auto.main()
lol_html_viewer_auto.organize_all_outputs()
