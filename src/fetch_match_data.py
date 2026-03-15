"""Fetch the latest LoL match and generate HTML viewer + CSV."""

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

import requests

# Ensure emoji and Japanese text print correctly on Windows (cp932 consoles).
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent))
from constants import PLATFORM_TO_REGION, QUEUE_PRESETS, load_env  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
ARCHIVE_DIR = DATA_DIR / "archive"


# ── Helpers ───────────────────────────────────────────────────────────────────


def _t(ja: str, en: str, lang: str) -> str:
    """Return ja or en string based on lang."""
    return ja if lang == "ja" else en


def _backup_if_exists(filename: str, lang: str) -> None:
    path = DATA_DIR / filename
    if path.exists():
        shutil.move(str(path), str(ARCHIVE_DIR / filename))
        print(_t(
            f"📦 既存ファイル {filename} を data/archive/ に移動しました",
            f"📦 Moved existing {filename} to data/archive/",
            lang,
        ))


def _get_json(url: str, headers: dict) -> requests.Response:
    return requests.get(url, headers=headers, timeout=30)


def _handle_error(res: requests.Response, context: str, lang: str) -> None:
    """Print a bilingual error for common HTTP status codes and exit."""
    messages: dict[int, str] = {
        401: _t(
            "❌ 401: APIキーの期限切れです。Riot Developer Portal でキーを再発行し、.env を更新してください\n"
            "   https://developer.riotgames.com/",
            "❌ 401: API key expired. Regenerate it at https://developer.riotgames.com/ and update .env",
            lang,
        ),
        403: _t(
            "❌ 403: APIキーが無効です。.env の内容を確認してください",
            "❌ 403: Invalid API key. Check the value in .env",
            lang,
        ),
        429: _t(
            "❌ 429: レート制限中です。少し待ってから再実行してください",
            "❌ 429: Rate limited. Wait a moment and try again",
            lang,
        ),
    }
    msg = messages.get(
        res.status_code,
        _t(
            f"❌ {context} 失敗：{res.status_code} {res.text}",
            f"❌ {context} failed: {res.status_code} {res.text}",
            lang,
        ),
    )
    print(msg)
    sys.exit(1)


# ── Entry point ───────────────────────────────────────────────────────────────


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Fetch latest LoL match and generate HTML viewer"
    )
    ap.add_argument(
        "--queue",
        "-q",
        default="swift",
        help=(
            "Queue to fetch. Named presets: swift (1700), ranked-solo (420), "
            "ranked-flex (440), normal-draft (400), normal-blind (430), aram (450). "
            "Or pass a numeric queue ID directly. Default: swift"
        ),
    )
    args = ap.parse_args()

    # ── Resolve queue ID ──────────────────────────────────────────────────────
    if args.queue.lstrip("-").isdigit():
        queue_id = int(args.queue)
    elif args.queue in QUEUE_PRESETS:
        queue_id = QUEUE_PRESETS[args.queue]
    else:
        print(
            f"❌ Unknown queue '{args.queue}'. "
            f"Available: {', '.join(QUEUE_PRESETS)} or a numeric ID"
        )
        sys.exit(1)

    # ── Load .env ─────────────────────────────────────────────────────────────
    env = load_env(ROOT / ".env")
    api_key = env.get("API_KEY", "")
    platform = env.get("PLATFORM", "JP1").upper()
    puuid = env.get("PUUID", "")
    lang = env.get("LANG", "ja").lower()
    region = PLATFORM_TO_REGION.get(platform, "asia")

    # ── Validate ──────────────────────────────────────────────────────────────
    if not api_key:
        raise RuntimeError(_t(
            "❌ API_KEY が .env に見つかりません — KEY=VALUE 形式で設定してください",
            "❌ API_KEY not found in .env — set it in KEY=VALUE format",
            lang,
        ))
    if not puuid:
        raise RuntimeError(_t(
            "❌ PUUID が .env に見つかりません — PUUID=your-puuid-here を追記してください",
            "❌ PUUID not found in .env — add PUUID=your-puuid-here",
            lang,
        ))
    if platform not in PLATFORM_TO_REGION:
        print(_t(
            f"[WARN] 不明な PLATFORM '{platform}' — asia にフォールバックします",
            f"[WARN] Unknown PLATFORM '{platform}' — falling back to asia",
            lang,
        ))

    headers = {"X-Riot-Token": api_key}
    os.makedirs(ARCHIVE_DIR, exist_ok=True)

    print(_t(
        f"🎮 対象キュー: {args.queue} (queue={queue_id})",
        f"🎮 Queue: {args.queue} (queue={queue_id})",
        lang,
    ))

    # ── Fetch match IDs ───────────────────────────────────────────────────────
    ids_url = (
        f"https://{region}.api.riotgames.com/lol/match/v5/matches/"
        f"by-puuid/{puuid}/ids?start=0&count=5&queue={queue_id}"
    )
    ids_res = _get_json(ids_url, headers)
    if ids_res.status_code != 200:
        _handle_error(ids_res, "match IDs", lang)

    match_ids = ids_res.json()
    if not match_ids:
        print(_t("❌ マッチIDが取得できませんでした", "❌ No match IDs returned", lang))
        sys.exit(1)

    match_id = match_ids[0]
    print(_t(f"✅ 最新のマッチID：{match_id}", f"✅ Latest match ID: {match_id}", lang))

    # ── Fetch match detail ────────────────────────────────────────────────────
    match_url = f"https://{region}.api.riotgames.com/lol/match/v5/matches/{match_id}"
    match_res = _get_json(match_url, headers)
    if match_res.status_code != 200:
        _handle_error(match_res, "match detail", lang)

    filename = f"{match_id}.json"
    _backup_if_exists(filename, lang)
    with open(DATA_DIR / filename, "w", encoding="utf-8") as f:
        json.dump(match_res.json(), f, ensure_ascii=False, indent=2)
    print(_t(f"📄 {filename} 保存完了！", f"📄 Saved {filename}", lang))

    # ── Fetch timeline ────────────────────────────────────────────────────────
    timeline_url = (
        f"https://{region}.api.riotgames.com/lol/match/v5/matches/{match_id}/timeline"
    )
    timeline_res = _get_json(timeline_url, headers)
    if timeline_res.status_code != 200:
        _handle_error(timeline_res, "timeline", lang)

    timeline_filename = f"{match_id}_timeline.json"
    _backup_if_exists(timeline_filename, lang)
    with open(DATA_DIR / timeline_filename, "w", encoding="utf-8") as f:
        json.dump(timeline_res.json(), f, ensure_ascii=False, indent=2)
    print(_t(f"⏱️ {timeline_filename} 保存完了！", f"⏱️ Saved {timeline_filename}", lang))

    # ── Generate HTML + CSV ───────────────────────────────────────────────────
    print(_t("\n📊 HTMLビューワーを生成します...", "\n📊 Generating HTML viewer...", lang))
    import lol_html_viewer_auto  # noqa: E402

    lol_html_viewer_auto.main([])  # pass empty argv → use defaults
    lol_html_viewer_auto.organize_all_outputs()


if __name__ == "__main__":
    main()
