#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=C0302,R0912,R0914,R0915,C0103,W0603,R0801
"""
LoL match + timeline JSON → HTML viewer + CSV.
Outputs ally/enemy stats table and timeline events (kills / objectives).
No external assets — fully self-contained dark-theme HTML.
"""

import argparse
import csv
import html
import json
import re
import shutil
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

# Ensure emoji and Japanese text print correctly on Windows (cp932 consoles).
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent))
from constants import (  # noqa: E402
    ALLOWED_EVENT_TYPES,
    LANE_NAMES,
    MONSTER_NAMES,
    PLATFORM_TO_REGION,
    load_env,
)

# ===== プロジェクトルートと各ディレクトリ =====
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "output"
ASSETS_DIR = ROOT / "assets"
_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


def _load_template(name: str) -> str:
    """Read and return a template file from src/templates/."""
    return (_TEMPLATES_DIR / name).read_text(encoding="utf-8")


def load_json(p: Path) -> dict:
    """Load and return a JSON file as a dict."""
    return json.load(p.open("r", encoding="utf-8"))


_env = load_env(ROOT / ".env")
USER_PUUID = _env.get("PUUID", "")
PLATFORM = _env.get("PLATFORM", "JP1").upper()
_LANG = _env.get(
    "LANG", "ja"
).lower()  # module-level default; overridden by --lang in main()

if PLATFORM not in PLATFORM_TO_REGION:
    print(
        f"[WARN] Unknown PLATFORM '{PLATFORM}' — falling back to JP1"
        if _LANG != "ja"
        else f"[WARN] 不明な PLATFORM '{PLATFORM}' — JP1 にフォールバックします"
    )
    PLATFORM = "JP1"

MATCH_RE = re.compile(rf"^{re.escape(PLATFORM)}_(\d+)\.json$")
TL_RE = re.compile(rf"^{re.escape(PLATFORM)}_(\d+)_timeline\.json$")


def pick_latest_pair(base_dir: Path) -> tuple[Path, Path]:
    """Return (match_path, timeline_path) for the most-recently modified match JSON in base_dir.

    Picks the newest ``{PLATFORM}_\\d+.json`` file as the match, then looks for the
    corresponding ``{PLATFORM}_\\d+_timeline.json``.  Falls back to the newest
    timeline file available if the exact pair is not found.

    Raises:
        FileNotFoundError: if no match JSON or no timeline JSON exists in base_dir.
    """
    files = [p for p in base_dir.iterdir() if p.is_file()]

    match_candidates = [p for p in files if MATCH_RE.match(p.name)]
    if not match_candidates:
        raise FileNotFoundError(f"No match JSON found: {base_dir}/{PLATFORM}_\\d+.json")

    match_path = max(match_candidates, key=lambda p: p.stat().st_mtime)
    game_id = MATCH_RE.match(match_path.name).group(1)

    timeline_path = base_dir / f"{PLATFORM}_{game_id}_timeline.json"
    if timeline_path.exists():
        return match_path, timeline_path

    tl_candidates = [p for p in files if TL_RE.match(p.name)]
    if not tl_candidates:
        raise FileNotFoundError(
            f"No timeline JSON found: {base_dir}/{PLATFORM}_\\d+_timeline.json"
        )

    fallback = max(tl_candidates, key=lambda p: p.stat().st_mtime)
    print(
        f"[WARN] 対応する timeline が見つかりません — 最新を使用: {fallback.name}"
        if _LANG == "ja"
        else f"[WARN] Matching timeline not found — using latest available: {fallback.name}"
    )
    return match_path, fallback


def pick_all_pairs(base_dir: Path) -> list[tuple[Path, Path]]:
    """Return all (match_path, timeline_path) pairs found in base_dir, sorted by mtime ascending.

    Skips match files whose corresponding timeline is missing.

    Args:
        base_dir: Directory to scan for ``{PLATFORM}_\\d+.json`` files.

    Returns:
        List of (match_path, timeline_path) tuples, oldest first.
    """
    files = {p.name: p for p in base_dir.iterdir() if p.is_file()}
    pairs = []
    for name, match_path in files.items():
        m = MATCH_RE.match(name)
        if not m:
            continue
        game_id = m.group(1)
        tl_name = f"{PLATFORM}_{game_id}_timeline.json"
        if tl_name not in files:
            print(
                f"⚠️  timeline なし → スキップ: {name}"
                if _LANG == "ja"
                else f"⚠️  no timeline — skipping: {name}"
            )
            continue
        pairs.append((match_path, files[tl_name]))
    pairs.sort(key=lambda pair: pair[0].stat().st_mtime)
    return pairs


def organize_all_outputs() -> None:
    """Move all but the newest output set (HTML + CSV) to output/archive/.

    Files are compared by mtime; anything older than the newest file by more
    than 1 second is treated as a previous run and archived.
    """
    archive_dir = OUTPUT_DIR / "archive"
    archive_dir.mkdir(exist_ok=True)

    all_files = sorted(
        [p for ext in ("*.csv", "*.html") for p in OUTPUT_DIR.glob(ext)],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    if not all_files:
        return

    latest_mtime = all_files[0].stat().st_mtime
    for p in all_files:
        if p.stat().st_mtime < latest_mtime - 1:
            dest = archive_dir / p.name
            try:
                shutil.move(str(p), str(dest))
                print(f"Moved to output/archive/: {p.name}")
            except Exception as e:  # pylint: disable=broad-exception-caught
                print(f"Error moving {p}: {e}")


def fmt_time(ms: int | None) -> str:
    """Convert milliseconds to a ``MM:SS`` string."""
    s = (ms or 0) // 1000
    return f"{s // 60:02d}:{s % 60:02d}"


def fetch_champ_map(dd_version: str, dd_locale: str) -> dict:
    """Fetch champion ID → name mapping from Data Dragon.

    Args:
        dd_version: Data Dragon patch version (e.g. ``"15.1.1"``).
        dd_locale:  Locale string (e.g. ``"ja_JP"`` or ``"en_US"``).

    Returns:
        Dict mapping champion key strings to localised display names.
        Returns an empty dict on network or parse errors.
    """
    url = f"https://ddragon.leagueoflegends.com/cdn/{dd_version}/data/{dd_locale}/champion.json"
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            dd_data = json.loads(r.read().decode("utf-8"))
        champ_map = {v["key"]: v["name"] for v in dd_data["data"].values()}
        print(
            f"[champ] {len(champ_map)} チャンプ名を Data Dragon {dd_version} ({dd_locale}) から取得"
            if _LANG == "ja"
            else f"[champ] Fetched {len(champ_map)} champions from Data Dragon {dd_version} ({dd_locale})"
        )
        return champ_map
    except Exception as e:  # pylint: disable=broad-exception-caught
        print(
            f"[WARN] Data Dragon の取得に失敗 ({e}) — チャンプ名は ID:xxx で表示されます"
            if _LANG == "ja"
            else f"[WARN] Data Dragon fetch failed ({e}) — champion names will show as ID:xxx"
        )
        return {}


class MatchContext:
    """Match state: participant lookup, event text, and row building."""

    def __init__(self, match: dict, champ_map: dict, user_puuid: str):
        self.participants = match["info"]["participants"]
        self.pid2p = {p["participantId"]: p for p in self.participants}
        self.champ_map = champ_map

        # Identify the user's participant and team
        self.user_pid: int | None = None
        self.user_team_id: int = 100
        for p in self.participants:
            if p.get("puuid") == user_puuid:
                self.user_pid = p["participantId"]
                self.user_team_id = p.get("teamId", 100)
                break
        if self.user_team_id not in (100, 200):
            self.user_team_id = 100

        self.friend_team_id = self.user_team_id
        self.enemy_team_id = 200 if self.friend_team_id == 100 else 100

        # Build once; avoids reconstructing the dict on every event_text() call.
        self._event_handlers = {
            "CHAMPION_KILL": self._champion_kill_text,
            "ELITE_MONSTER_KILL": self._elite_monster_text,
            "BUILDING_KILL": self._building_text,
        }

    # ── Lookup helpers ────────────────────────────────────────────────────

    def champ_name(self, champ_id: int) -> str:
        """Return the localised champion name for a champion ID, or ``"ID:<n>"`` if unknown."""
        return self.champ_map.get(str(champ_id), f"ID:{champ_id}")

    def get_p(self, pid: int | None) -> dict | None:
        """Safe participant lookup (timeline events may have 0 / None)."""
        if not isinstance(pid, int) or pid <= 0:
            return None
        return self.pid2p.get(pid)

    def champ_from_pid(self, pid, lang: str = "ja") -> str:
        """Return the champion name for a participant ID, in the requested language.

        Falls back to ``"不明"`` / ``"Unknown"`` when the participant is not found.
        """
        p = self.get_p(pid)
        if not p:
            return "不明" if lang == "ja" else "Unknown"
        if lang == "en":
            return p.get("championName") or self.champ_name(p.get("championId"))
        return self.champ_name(p.get("championId"))

    @staticmethod
    def display_name(p: dict) -> str:
        """Return the best available display name for a participant.

        Prefers ``riotIdGameName#riotIdTagline``; falls back to ``summonerName``,
        bare game name, or ``PID:<n>`` as a last resort.
        """
        gn = p.get("riotIdGameName") or ""
        tl = p.get("riotIdTagline") or ""
        if gn and tl:
            return f"{gn}#{tl}"
        return p.get("summonerName") or gn or f"PID:{p.get('participantId')}"

    def team_label(self, team_id: int, lang: str = "ja") -> str:
        """Return ``"味方"/"Ally"`` or ``"敵"/"Enemy"`` relative to the user's team."""
        if team_id == self.user_team_id:
            return "味方" if lang == "ja" else "Ally"
        if team_id in (100, 200):
            return "敵" if lang == "ja" else "Enemy"
        return ""

    # ── Event text ────────────────────────────────────────────────────────

    def event_text(self, ev: dict, lang: str = "ja") -> str:
        """Return a human-readable description of a timeline event.

        Dispatches to the appropriate ``_*_text`` method based on ``ev["type"]``.
        Returns an empty string for unrecognised event types.
        """
        handler = self._event_handlers.get(ev.get("type", ""))
        return handler(ev, lang) if handler else ""

    def _champion_kill_text(self, ev: dict, lang: str) -> str:
        """Format a CHAMPION_KILL event as a human-readable string."""
        killer = self.champ_from_pid(ev.get("killerId"), lang)
        victim = self.champ_from_pid(ev.get("victimId"), lang)
        return f"⚔️ {killer}が{victim}をキル" if lang == "ja" else f"⚔️ {killer} killed {victim}"

    def _elite_monster_text(self, ev: dict, lang: str) -> str:
        """Format an ELITE_MONSTER_KILL event as a human-readable string."""
        killer = self.champ_from_pid(ev.get("killerId"), lang)
        monster = ev.get("monsterType", "")
        sub = ev.get("monsterSubType", "")
        icon = "🐉" if monster == "DRAGON" else "👑"

        entry = MONSTER_NAMES.get(monster)
        if entry:
            m = entry[lang]
        else:
            m = monster or ("オブジェクト" if lang == "ja" else "Monster")

        if sub:
            m = f"{m}（{sub}）" if lang == "ja" else f"{m} ({sub})"
        return f"{icon} {killer}が{m}を討伐" if lang == "ja" else f"{icon} {killer} slew {m}"

    def _building_text(self, ev: dict, lang: str) -> str:
        """Format a BUILDING_KILL event as a human-readable string."""
        killer_id = ev.get("killerId") or 0
        if killer_id == 0:
            killer = "ミニオン" if lang == "ja" else "Minion"
        else:
            killer = self.champ_from_pid(killer_id, lang)
        building = ev.get("buildingType", "")
        lane = ev.get("laneType", "")

        if building == "TOWER_BUILDING":
            icon, b_ja, b_en = "🏰", "タワー", "Tower"
        elif building == "INHIBITOR_BUILDING":
            icon, b_ja, b_en = "💎", "インヒビター", "Inhibitor"
        else:
            icon, b_ja, b_en = "🏗️", building or "建物", building or "Building"

        lane_entry = LANE_NAMES.get(lane)
        if lane_entry:
            lane_label = lane_entry[lang]
        else:
            lane_label = ""

        if lang == "ja":
            suffix = f"（{lane_label}）" if lane_label else ""
            return f"{icon} {killer}が{b_ja}{suffix}を破壊"
        else:
            suffix = f" ({lane_label})" if lane_label else ""
            return f"{icon} {killer} destroyed {b_en}{suffix}"

    # ── Data builders ─────────────────────────────────────────────────────

    def build_player_row(self, p: dict) -> dict:
        """Build one player stats row dict."""
        k = p.get("kills", 0)
        d = p.get("deaths", 0)
        a = p.get("assists", 0)
        cs = (p.get("totalMinionsKilled", 0) or 0) + (p.get("neutralMinionsKilled", 0) or 0)
        return {
            "teamId": p.get("teamId"),
            "team": self.team_label(p.get("teamId")),
            "pos": p.get("teamPosition") or p.get("individualPosition") or "",
            "player": self.display_name(p),
            "champ": self.champ_name(p.get("championId")),
            "champName": p.get("championName", ""),
            "pid": p.get("participantId"),
            "k": k,
            "d": d,
            "a": a,
            "kda": (k + a) / max(1, d),
            "cs": cs,
            "gold": p.get("goldEarned", 0) or 0,
            "dmg": p.get("totalDamageDealtToChampions", 0) or 0,
            "taken": p.get("totalDamageTaken", 0) or 0,
            "vision": p.get("visionScore", 0) or 0,
            "cc": p.get("timeCCingOthers", 0) or 0,
            "kp": p.get("challenges", {}).get("killParticipation", 0) or 0,
            "dead_s": p.get("totalTimeSpentDead", 0) or 0,
            "win": bool(p.get("win", False)),
            "is_user": (p.get("participantId") == self.user_pid),
        }

    def build_all_rows(self) -> tuple[list, list, list, list]:
        """Return (team100, team200, friend_rows, enemy_rows)."""
        team100 = [self.build_player_row(p) for p in self.participants if p.get("teamId") == 100]
        team200 = [self.build_player_row(p) for p in self.participants if p.get("teamId") == 200]
        friend_rows = team100 if self.friend_team_id == 100 else team200
        enemy_rows = team200 if self.friend_team_id == 100 else team100
        return team100, team200, friend_rows, enemy_rows

    def build_events(self, timeline: dict, lang: str = "ja") -> list:
        """Parse timeline frames and return filtered, sorted event list."""
        events = []
        for frame in timeline["info"]["frames"]:
            for ev in frame.get("events", []) or []:
                if ev.get("type") not in ALLOWED_EVENT_TYPES:
                    continue
                ts = ev.get("timestamp", 0) or 0
                team_id = self._event_team_id(ev)
                user_involved = self.user_pid is not None and self.user_pid in [
                    ev.get("killerId"), ev.get("victimId"),
                    ev.get("creatorId"), ev.get("participantId"),
                ]
                text_ja = self.event_text(ev, "ja")
                text_en = self.event_text(ev, "en")
                if not text_ja:
                    continue
                events.append({
                    "t": ts,
                    "time": fmt_time(ts),
                    "type": ev.get("type", ""),
                    "teamId": team_id,
                    "team": self.team_label(team_id, "ja") if team_id else "",
                    "team_en": self.team_label(team_id, "en") if team_id else "",
                    "text": text_ja,
                    "text_en": text_en,
                    "is_user": user_involved,
                })
        events.sort(key=lambda x: x["t"])
        return events

    def _event_team_id(self, ev: dict) -> int | None:
        """Return the teamId of the primary actor in a timeline event.

        Checks ``participantId``, ``killerId``, ``creatorId``, and ``victimId``
        in order, returning the teamId of the first valid participant found.
        Returns ``None`` if no participant can be resolved.
        """
        for pid_key in ("participantId", "killerId", "creatorId", "victimId"):
            p = self.get_p(ev.get(pid_key))
            if p:
                return p.get("teamId")
        return None

    def build_gold_frames(self, timeline: dict) -> list:
        """Extract per-frame team gold differential for the gold lead chart."""
        pid_to_team = {p["participantId"]: p["teamId"] for p in self.participants}
        gold_frames = []
        for frame in timeline["info"].get("frames", []):
            ts = frame.get("timestamp", 0) // 1000
            pf = frame.get("participantFrames", {})
            friend_g = sum(
                pf[str(pid)].get("totalGold", 0)
                for pid in pid_to_team
                if pid_to_team[pid] == self.friend_team_id and str(pid) in pf
            )
            enemy_g = sum(
                pf[str(pid)].get("totalGold", 0)
                for pid in pid_to_team
                if pid_to_team[pid] != self.friend_team_id and str(pid) in pf
            )
            gold_frames.append({"t": ts, "diff": friend_g - enemy_g})
        return gold_frames


def html_escape(s: str) -> str:
    """Escape a value for safe inclusion in HTML text or attribute values."""
    return html.escape(str(s), quote=True)


def table_html(rows: list[dict], title_key: str, team_id: int) -> str:
    """Render a player stats table as an HTML ``<section>`` string.

    Args:
        rows:      List of player row dicts produced by ``MatchContext.build_player_row``.
        title_key: i18n key — ``"ally_team"`` or ``"enemy_team"``.
        team_id:   Numeric team ID (100 or 200) written to ``data-i18n-team``.

    Returns:
        An HTML fragment containing a ``<section class="card">`` with a ``<table>``.
    """
    title_ja = "味方チーム" if title_key == "ally_team" else "敵チーム"
    head = [
        "POS",
        "Player",
        "Champion",
        "K/D/A",
        "KDA",
        "CS",
        "Gold",
        "DMG",
        "Vision",
        "CC",
    ]
    trs = []
    for r in rows:
        cls = "user" if r["is_user"] else ""
        trs.append(
            f"<tr class='{cls}'>"
            f"<td>{html_escape(r['pos'])}</td>"
            f"<td>{html_escape(r['player'])}</td>"
            f"<td data-champ-en=\"{html_escape(r['champName'])}\">{html_escape(r['champ'])}</td>"
            f"<td>{r['k']}/{r['d']}/{r['a']}</td>"
            f"<td>{r['kda']:.2f}</td>"
            f"<td>{r['cs']}</td>"
            f"<td>{r['gold']}</td>"
            f"<td>{r['dmg']}</td>"
            f"<td>{r['vision']}</td>"
            f"<td>{r['cc']}</td>"
            f"</tr>"
        )
    return f"""
        <section class=\"card\">
          <h2 data-i18n=\"{title_key}\" data-i18n-team=\"{team_id}\">{html_escape(title_ja)}</h2>
          <div class=\"table-wrap\">
            <table>
              <thead><tr>{''.join(f'<th>{h}</th>' for h in head)}</tr></thead>
              <tbody>{''.join(trs)}</tbody>
            </table>
          </div>
        </section>
        """


def build_html(
    ctx: MatchContext,
    match: dict,
    match_path: Path,
    timeline_path: Path,
    friend_rows: list[dict],
    enemy_rows: list[dict],
    events: list[dict],
    gold_frames: list[dict],
    dd_version: str,
    lang: str,
) -> str:
    """Build and return the full self-contained HTML document as a string.

    Inlines ``style.css`` and ``main.js`` from ``src/templates/``, injects
    all match data as JSON constants, and assembles stats tables, chart canvases,
    and the timeline event log into a single dark-theme HTML page.

    Args:
        ctx:           Populated ``MatchContext`` for participant/team lookups.
        match:         Raw match detail JSON (``JP1_*.json``).
        match_path:    Path to the match JSON file (used in the footer metadata).
        timeline_path: Path to the timeline JSON file (used in the footer metadata).
        friend_rows:   Player row dicts for the user's team.
        enemy_rows:    Player row dicts for the opposing team.
        events:        Filtered/sorted timeline event list.
        gold_frames:   Per-frame gold differential list.
        dd_version:    Data Dragon version string (e.g. ``"15.1.1"``).
        lang:          Display language — ``"ja"`` or ``"en"``.

    Returns:
        A complete ``<!doctype html>`` string ready to write to disk.
    """
    friend_team_id = ctx.friend_team_id
    enemy_team_id = ctx.enemy_team_id

    events_json = json.dumps(events, ensure_ascii=False)
    players_json = json.dumps(
        [
            {
                "champ": r["champ"],
                "champName": r["champName"],
                "player": r["player"],
                "k": r["k"],
                "d": r["d"],
                "a": r["a"],
                "kda": round(r["kda"], 4),
                "cc": r["cc"],
                "dmg": r["dmg"],
                "taken": r["taken"],
                "gold": r["gold"],
                "cs": r["cs"],
                "vision": r["vision"],
                "kp": round(r["kp"], 4),
                "dead_s": r["dead_s"],
                "pid": r["pid"],
                "teamId": r["teamId"],
                "is_user": r["is_user"],
            }
            for r in friend_rows + enemy_rows
        ],
        ensure_ascii=False,
    )

    game_info = match["info"]
    game_duration = game_info.get("gameDuration", 1) or 1
    gold_frames_json = json.dumps(gold_frames, ensure_ascii=False)

    meta = (
        f"Mode: {game_info.get('gameMode','')} / "  # noqa: E501,E231,E228
        f"Duration: {game_info.get('gameDuration',0)//60}:{game_info.get('gameDuration',0)%60:02d} / "  # noqa: E501,E231,E228
        f"Version: {game_info.get('gameVersion','')}"  # noqa: E501,E231,E228
    )

    used_files = f"match: {match_path.name} / timeline: {timeline_path.name} / champ: ddragon {dd_version}"

    css = _load_template("style.css")
    main_js_content = _load_template("main.js")

    return f"""<!doctype html>
<html lang=\"ja\">
<head>
<meta charset=\"utf-8\"/>
<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"/>
<title>LoL Match Viewer - {html_escape(match['metadata'].get('matchId',''))}</title>
<style>
{css}
</style>
</head>
<body>
<header>
  <h1>LoL Match Viewer — {html_escape(match['metadata'].get('matchId',''))}</h1>
  <div class=\"meta\">{html_escape(meta)}</div>
  <div class=\"meta\">{html_escape(used_files)}</div>
  <button id=\"lang-toggle\" onclick=\"toggleLang()\">🌐 EN</button>
</header>

<main>
  {table_html(friend_rows, "ally_team", friend_team_id)}
  {table_html(enemy_rows,  "enemy_team", enemy_team_id)}

  <div class=\"charts-wrap\">
    <section class=\"card chart-full\"><p class=\"chart-label\" data-i18n=\"chart_kda_breakdown\">KDA 内訳</p>
      <canvas id=\"chart-kda-breakdown\"></canvas></section>
    <section class=\"card\"><p class=\"chart-label\" data-i18n=\"chart_kda_ratio\">KDA 比率</p>
      <canvas id=\"chart-kda-ratio\"></canvas></section>
    <section class=\"card\"><p class=\"chart-label\" data-i18n=\"chart_dmg\">ダメージ</p>
      <canvas id=\"chart-dmg\"></canvas></section>
    <section class=\"card\"><p class=\"chart-label\" data-i18n=\"chart_gold\">ゴールド</p>
      <canvas id=\"chart-gold\"></canvas></section>
    <section class=\"card\"><p class=\"chart-label\" data-i18n=\"chart_cs\">CS</p>
      <canvas id=\"chart-cs\"></canvas></section>
    <section class=\"card\"><p class=\"chart-label\" data-i18n=\"chart_vision\">視界スコア</p>
      <canvas id=\"chart-vision\"></canvas></section>
    <section class=\"card\"><p class=\"chart-label\" data-i18n=\"chart_cc\">CC タイム（秒）</p>
      <canvas id=\"chart-cc\"></canvas></section>
    <section class=\"card chart-full\"><p class=\"chart-label\" data-i18n=\"chart_scatter\">与ダメ / 被ダメ 分布</p>
      <canvas id=\"chart-scatter\"></canvas></section>
    <div class=\"radar-wrap\">
      <section class=\"card\"><p class=\"chart-label\" data-i18n=\"chart_radar_ally\">味方チーム — パフォーマンス</p>
        <canvas id=\"chart-radar-friend\"></canvas></section>
      <section class=\"card\"><p class=\"chart-label\" data-i18n=\"chart_radar_enemy\">敵チーム — パフォーマンス</p>
        <canvas id=\"chart-radar-enemy\"></canvas></section>
    </div>
    <div class=\"radar-wrap\">
      <section class=\"card\"><p class=\"chart-label\" data-i18n=\"chart_kp\">キルへの関与率（KP%）</p>
        <canvas id=\"chart-kp\"></canvas></section>
      <section class=\"card\"><p class=\"chart-label\" data-i18n=\"chart_dead\">デス時間（試合時間比% ／ 低いほど良）</p>
        <canvas id=\"chart-dead\"></canvas></section>
    </div>
    <section class=\"card chart-full\"><p class=\"chart-label\" data-i18n=\"chart_gold_diff\">チームゴールドリード 推移</p>
      <canvas id=\"chart-gold-diff\"></canvas></section>
  </div>

  <section class=\"card\">
    <h2 data-i18n=\"timeline_title\">時系列イベント（キル / オブジェクト）</h2>
    <div class=\"toolbar\">
      <input id=\"q\" data-i18n-placeholder=\"search_ph\" placeholder=\"検索: 例) キル / ドラゴン / ワード / ルル など\" style=\"flex:1; min-width: 260px;\">
      <select id=\"team\">
        <option value=\"\" data-i18n=\"team_all\">Team: 全部</option>
        <option value=\"{friend_team_id}\" data-i18n=\"team_ally\">味方</option>
        <option value=\"{enemy_team_id}\" data-i18n=\"team_enemy\">敵</option>
      </select>
      <select id=\"type\">
        <option value=\"\" data-i18n=\"type_all\">Type: 全部</option>
      </select>
    </div>

    <div class=\"toolbar\" style=\"margin-top:10px;\">
      <span class=\"pill\"><span class=\"dot blue\"></span><span data-i18n=\"team_ally\">味方</span></span>
      <span class=\"pill\"><span class=\"dot red\"></span><span data-i18n=\"team_enemy\">敵</span></span>
      <span class=\"pill\"><span data-i18n=\"pill_count\">イベント件数</span>: <span id=\"count\">0</span></span>
    </div>

    <div id=\"events\" class=\"events\"></div>
  </section>
</main>

<footer>generated locally — no external assets</footer>

<script>
// --- injected data ---
const EVENTS   = {events_json};
const PLAYERS  = {players_json};
const GOLD_FRAMES = {gold_frames_json};
const GAME_DURATION = {game_duration};
const FRIEND_TEAM_ID = {friend_team_id};
const ENEMY_TEAM_ID = {enemy_team_id};
const DD_VERSION = "{dd_version}";
</script>
<script>
{main_js_content}
</script>
</body>
</html>
"""


def write_csv(
    team100: list[dict],
    team200: list[dict],
    events: list[dict],
    out_team: Path,
    out_events: Path,
) -> None:
    """Write player stats and timeline events to two CSV files.

    Args:
        team100:    Player row dicts for team 100.
        team200:    Player row dicts for team 200.
        events:     Filtered timeline event list from ``MatchContext.build_events``.
        out_team:   Destination path for the team stats CSV.
        out_events: Destination path for the events CSV.
    """
    with out_team.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "teamId",
                "team",
                "pos",
                "player",
                "champ",
                "kills",
                "deaths",
                "assists",
                "kda",
                "cs",
                "gold",
                "dmg",
                "vision",
                "cc",
                "kp",
                "dead_s",
                "win",
                "is_user",
            ]
        )
        for r in team100 + team200:
            w.writerow(
                [
                    r["teamId"],
                    r["team"],
                    r["pos"],
                    r["player"],
                    r["champ"],
                    r["k"],
                    r["d"],
                    r["a"],
                    f"{r['kda']:.4f}",
                    r["cs"],
                    r["gold"],
                    r["dmg"],
                    r["vision"],
                    r["cc"],
                    f"{r['kp']:.4f}",
                    r["dead_s"],
                    int(r["win"]),
                    int(r["is_user"]),
                ]
            )

    with out_events.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["t_ms", "time", "teamId", "team", "type", "text"])
        for e in events:
            w.writerow(
                [
                    e["t"],
                    e["time"],
                    e["teamId"],
                    e["team"],
                    e["type"],
                    e["text"],
                ]
            )


def _process_one_pair(
    match_path: Path,
    timeline_path: Path,
    no_csv: bool,
    lang: str,
    stem: str | None = None,
) -> None:
    """Load a single JSON pair and write the HTML (and optionally CSV) to output/.

    Args:
        match_path:    Path to the match detail JSON.
        timeline_path: Path to the matching timeline JSON.
        no_csv:        When ``True``, skip writing CSV files.
        lang:          Display language (``"ja"`` or ``"en"``).
        stem:          Output filename stem (e.g. ``"JP1_566188687"``).
                       When ``None``, a timestamp string is used instead.
    """
    match = load_json(match_path)
    timeline = load_json(timeline_path)

    gv_parts = match["info"].get("gameVersion", "0.0").split(".")[:2]
    dd_version = ".".join(gv_parts) + ".1"
    dd_locale = "en_US" if lang == "en" else "ja_JP"
    champ_map = fetch_champ_map(dd_version, dd_locale)

    ctx = MatchContext(match, champ_map, USER_PUUID)
    team100, team200, friend_rows, enemy_rows = ctx.build_all_rows()
    events = ctx.build_events(timeline, lang)
    gold_frames = ctx.build_gold_frames(timeline)

    html_doc = build_html(ctx, match, match_path, timeline_path,
                          friend_rows, enemy_rows, events, gold_frames, dd_version, lang)

    OUTPUT_DIR.mkdir(exist_ok=True)
    name = stem or datetime.now().strftime("%Y%m%d%H%M%S")
    out_html = OUTPUT_DIR / f"out_{name}.html"
    out_html.write_text(html_doc, encoding="utf-8")

    if not no_csv:
        out_team = OUTPUT_DIR / f"out_{name}_team.csv"
        out_events = OUTPUT_DIR / f"out_{name}_events.csv"
        write_csv(team100, team200, events, out_team, out_events)

    print("wrote:")
    print(" ", out_html)
    if not no_csv:
        print(" ", out_team)
        print(" ", out_events)
    print("used:")
    print(" ", match_path)
    print(" ", timeline_path)


def main(argv=None):
    """CLI entry point: parse args, load JSONs, generate HTML + CSV, print paths.

    Args:
        argv: Argument list passed to ``ArgumentParser.parse_args``.
              ``None`` reads from ``sys.argv`` (standard CLI behaviour).
              Pass ``[]`` to use all defaults (e.g. when called from ``fetch_match_data``).
    """
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--dir",
        default=str(DATA_DIR),
        help="Directory containing match JSON files (default: data/)",
    )
    ap.add_argument("--no-csv", action="store_true", help="Skip CSV output — generate HTML only")
    ap.add_argument(
        "--lang",
        default="ja",
        choices=["ja", "en"],
        help="Champion name language for the table (default: ja)",
    )
    ap.add_argument(
        "--all",
        action="store_true",
        dest="all_pairs",
        help="Convert every match pair in --dir to HTML (default: latest only)",
    )
    ap.add_argument(
        "--count",
        "-n",
        type=int,
        default=None,
        metavar="N",
        help="Used with --all: process only the N most recent matches (e.g. --all -n 10)",
    )
    args = ap.parse_args(argv)

    global _LANG
    _LANG = args.lang

    base_dir = Path(args.dir).expanduser().resolve()

    if args.all_pairs:
        pairs = pick_all_pairs(base_dir)
        if not pairs:
            print(
                "❌ JSONペアが見つかりませんでした" if args.lang == "ja"
                else "❌ No JSON pairs found"
            )
            return
        if args.count is not None:
            pairs = pairs[-args.count:]   # newest N (list is sorted oldest-first)
        total = len(pairs)
        print(
            f"📂 {total} 試合分のHTMLを生成します..." if args.lang == "ja"
            else f"📂 Generating HTML for {total} matches..."
        )
        for i, (match_path, timeline_path) in enumerate(pairs, 1):
            print(f"\n[{i}/{total}] {match_path.name}")
            stem = MATCH_RE.match(match_path.name).group(0).removesuffix(".json")
            _process_one_pair(match_path, timeline_path, args.no_csv, args.lang, stem=stem)
        print(
            f"\n✅ {total} 試合のHTML生成完了 → output/" if args.lang == "ja"
            else f"\n✅ Done — {total} HTML files written to output/"
        )
        return True  # caller should skip organize_all_outputs in batch mode
    else:
        match_path, timeline_path = pick_latest_pair(base_dir)
        _process_one_pair(match_path, timeline_path, args.no_csv, args.lang)
    return False


if __name__ == "__main__":
    if not main():
        organize_all_outputs()
