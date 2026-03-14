#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LoL match + timeline JSON から
- 味方/敵の一覧表（基本スタッツ）
- 時系列イベントビュー（キル / オブジェクト / ワードのみ・日本語）
を1枚HTMLに出力する（+ CSVも出力）。

今回の改修内容:
- タイムラインイベントは以下のみ採用
  * CHAMPION_KILL
  * ELITE_MONSTER_KILL
  * BUILDING_KILL
  * WARD_PLACED
  * WARD_KILL
- イベント文言を日本語で簡潔化（例: "02:44 オラフがガレンをキル"）
- killerId / victimId / creatorId が 0 や None で participant を引けないケースを安全に処理（"不明"）
"""

import json, html, argparse, csv, re
from pathlib import Path
from datetime import datetime
import os
import shutil
import glob

# ===== プロジェクトルートと各ディレクトリ =====
ROOT       = Path(__file__).resolve().parent.parent
DATA_DIR   = ROOT / "data"
OUTPUT_DIR = ROOT / "output"
ASSETS_DIR = ROOT / "assets"

# ===== .env パーサー =====
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

PLATFORM_TO_REGION = {
    "BR1": "americas", "LA1": "americas", "LA2": "americas", "NA1": "americas",
    "EUN1": "europe",  "EUW1": "europe",  "TR1": "europe",   "RU": "europe",
    "JP1": "asia",     "KR": "asia",
    "OC1": "sea",      "PH2": "sea",      "SG2": "sea",
    "TH2": "sea",      "TW2": "sea",      "VN2": "sea",
}

_env       = load_env(ROOT / ".env")
USER_PUUID = _env.get("PUUID", "")
PLATFORM   = _env.get("PLATFORM", "JP1").upper()
if PLATFORM not in PLATFORM_TO_REGION:
    print(f"[WARN] 不明な PLATFORM '{PLATFORM}' — JP1 にフォールバック")
    PLATFORM = "JP1"

# ===== 固定値 =====
CHAMP_FILE = ASSETS_DIR / "00_champ.json"

MATCH_RE = re.compile(rf"^{re.escape(PLATFORM)}_(\d+)\.json$")
TL_RE    = re.compile(rf"^{re.escape(PLATFORM)}_(\d+)_timeline\.json$")

ALLOWED_EVENT_TYPES = {
    "CHAMPION_KILL",
    "ELITE_MONSTER_KILL",
    "BUILDING_KILL",
}

def organize_all_outputs():
    archive_dir = OUTPUT_DIR / "archive"
    archive_dir.mkdir(exist_ok=True)

    # 対象拡張子のリスト
    extensions = ["*.csv", "*.html"]
    all_files = []
    for ext in extensions:
        all_files.extend(glob.glob(str(OUTPUT_DIR / ext)))

    if not all_files:
        return

    # 更新日時でソート（新しい順）
    all_files.sort(key=os.path.getmtime, reverse=True)

    # 【重要】最新の「セット」を残すロジック
    # ここでは、最も新しいファイル1件（最新のHTMLかCSV）を基準とし、
    # それ以外の古いタイムスタンプを持つファイルを移動させます。
    latest_time = os.path.getmtime(all_files[0])
    
    for f in all_files:
        # 最新ファイル（またはそれとほぼ同時刻に生成されたファイル）以外を移動
        # 1秒程度の誤差は許容範囲として判定
        if os.path.getmtime(f) < latest_time - 1:
            dest = archive_dir / os.path.basename(f)
            try:
                shutil.move(f, str(dest))
                print(f"Moved to output/archive/: {os.path.basename(f)}")
            except Exception as e:
                print(f"Error moving {f}: {e}")

def fmt_time(ms: int) -> str:
    s = (ms or 0) // 1000
    return f"{s//60:02d}:{s%60:02d}"


def load_json(p: Path):
    return json.load(p.open("r", encoding="utf-8"))


def pick_latest_pair(base_dir: Path) -> tuple[Path, Path]:
    """同フォルダの中の最新の JP1_\d+.json を match として採用し、対応timelineを探す。"""
    files = [p for p in base_dir.iterdir() if p.is_file()]

    match_candidates = [p for p in files if MATCH_RE.match(p.name)]
    if not match_candidates:
        raise FileNotFoundError(f"match が見つからない: {base_dir}/{PLATFORM}_\\d+.json")

    match_path = max(match_candidates, key=lambda p: p.stat().st_mtime)
    game_id = MATCH_RE.match(match_path.name).group(1)

    timeline_path = base_dir / f"{PLATFORM}_{game_id}_timeline.json"
    if timeline_path.exists():
        return match_path, timeline_path

    tl_candidates = [p for p in files if TL_RE.match(p.name)]
    if not tl_candidates:
        raise FileNotFoundError(f"timeline が見つからない: {base_dir}/{PLATFORM}_\\d+_timeline.json")

    fallback = max(tl_candidates, key=lambda p: p.stat().st_mtime)
    print(f"[WARN] 対応する timeline が見つからないため、最新 timeline を採用: {fallback.name}")
    return match_path, fallback


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=str(DATA_DIR), help="JSONが置いてあるディレクトリ（デフォルト: data/）")
    ap.add_argument("--no-csv", action="store_true", help="CSVを出さない（HTMLのみ）")
    args = ap.parse_args()

    base_dir = Path(args.dir).expanduser().resolve()

    match_path, timeline_path = pick_latest_pair(base_dir)
    champ_path = CHAMP_FILE
    if not champ_path.exists():
        raise FileNotFoundError(f"champ が見つからない: {champ_path}")

    match = load_json(match_path)
    timeline = load_json(timeline_path)
    champ_map = load_json(champ_path)

    def champ_name(champ_id: int) -> str:
        return champ_map.get(str(champ_id), f"ID:{champ_id}")

    participants = match["info"]["participants"]
    pid2p = {p["participantId"]: p for p in participants}

    user_pid = None
    user_team_id = None
    for p in participants:
        if p.get("puuid") == USER_PUUID:
            user_pid = p["participantId"]
            user_team_id = p.get("teamId")
            break

    # 念のため: ユーザーが見つからない場合は teamId=100 を味方として扱う
    if user_team_id not in (100, 200):
        user_team_id = 100

    def display_name(p):
        gn = p.get("riotIdGameName") or ""
        tl = p.get("riotIdTagline") or ""
        if gn and tl:
            return f"{gn}#{tl}"
        return (p.get("summonerName") or gn or f"PID:{p.get('participantId')}")

    def team_label(team_id: int) -> str:
        if team_id == user_team_id:
            return "味方"
        if team_id in (100, 200):
            return "敵"
        return ""

    def team_label_en(team_id: int) -> str:
        if team_id == user_team_id:
            return "Ally"
        if team_id in (100, 200):
            return "Enemy"
        return ""

    def row_for(p):
        k, d, a = p.get("kills", 0), p.get("deaths", 0), p.get("assists", 0)
        cs = (p.get("totalMinionsKilled", 0) or 0) + (p.get("neutralMinionsKilled", 0) or 0)
        dmg = p.get("totalDamageDealtToChampions", 0) or 0
        taken = p.get("totalDamageTaken", 0) or 0
        gold = p.get("goldEarned", 0) or 0
        vs = p.get("visionScore", 0) or 0
        cc = p.get("timeCCingOthers", 0) or 0
        pos = p.get("teamPosition") or p.get("individualPosition") or ""
        champ_en = p.get("championName", "")
        kp = p.get("challenges", {}).get("killParticipation", 0) or 0
        dead_s = p.get("totalTimeSpentDead", 0) or 0
        return {
            "teamId": p.get("teamId"),
            "team": team_label(p.get("teamId")),
            "pos": pos,
            "player": display_name(p),
            "champ": champ_name(p.get("championId")),
            "champName": champ_en,
            "pid": p.get("participantId"),
            "k": k, "d": d, "a": a,
            "kda": (k + a) / max(1, d),
            "cs": cs,
            "gold": gold,
            "dmg": dmg,
            "taken": taken,
            "vision": vs,
            "cc": cc,
            "kp": kp,
            "dead_s": dead_s,
            "is_user": (p.get("participantId") == user_pid),
        }

    team100 = [row_for(p) for p in participants if p.get("teamId") == 100]
    team200 = [row_for(p) for p in participants if p.get("teamId") == 200]

    # ユーザー基準で味方/敵を振り分け
    friend_team_id = user_team_id
    enemy_team_id = 200 if friend_team_id == 100 else 100
    friend_rows = team100 if friend_team_id == 100 else team200
    enemy_rows  = team200 if friend_team_id == 100 else team100

    def get_p(pid):
        # timelineイベントには 0 / None が入ることがあるので安全に
        if not isinstance(pid, int) or pid <= 0:
            return None
        return pid2p.get(pid)

    def champ_from_pid(pid) -> str:
        p = get_p(pid)
        if not p:
            return "不明"
        return champ_name(p.get("championId"))

    def champ_from_pid_en(pid) -> str:
        p = get_p(pid)
        if not p:
            return "Unknown"
        return p.get("championName") or champ_name(p.get("championId"))

    def short_p(pid):
        p = get_p(pid)
        if not p:
            return "不明"
        return f"{champ_name(p.get('championId'))}({display_name(p)})"

    def event_to_text_en(ev):
        t = ev.get("type", "")

        if t == "CHAMPION_KILL":
            killer = champ_from_pid_en(ev.get("killerId"))
            victim = champ_from_pid_en(ev.get("victimId"))
            return f"⚔️ {killer} killed {victim}"

        if t == "ELITE_MONSTER_KILL":
            killer = champ_from_pid_en(ev.get("killerId"))
            monster = ev.get("monsterType", "")
            sub = ev.get("monsterSubType", "")
            name_map = {
                "DRAGON": "Dragon",
                "BARON_NASHOR": "Baron Nashor",
                "RIFTHERALD": "Rift Herald",
            }
            m = name_map.get(monster, monster or "Monster")
            if sub:
                m = f"{m} ({sub})"
            icon = "🐉" if monster == "DRAGON" else "👑"
            return f"{icon} {killer} slew {m}"

        if t == "BUILDING_KILL":
            killer = champ_from_pid_en(ev.get("killerId"))
            building = ev.get("buildingType", "")
            lane = ev.get("laneType", "")
            if building == "TOWER_BUILDING":
                icon = "🏰"
                b = "Tower"
            elif building == "INHIBITOR_BUILDING":
                icon = "💎"
                b = "Inhibitor"
            else:
                icon = "🏗️"
                b = building or "Building"
            lane_map = {
                "TOP_LANE": "Top",
                "MID_LANE": "Mid",
                "BOT_LANE": "Bot",
            }
            l = lane_map.get(lane, "")
            suffix = f" ({l})" if l else ""
            return f"{icon} {killer} destroyed {b}{suffix}"

        if t == "WARD_PLACED":
            who = champ_from_pid_en(ev.get("creatorId"))
            return f"👁️ {who} placed a ward"

        if t == "WARD_KILL":
            who = champ_from_pid_en(ev.get("killerId"))
            return f"🧹 {who} destroyed a ward"

        return ""

    def event_to_text(ev):
        t = ev.get("type", "")

        if t == "CHAMPION_KILL":
            killer = champ_from_pid(ev.get("killerId"))
            victim = champ_from_pid(ev.get("victimId"))
            return f"⚔️ {killer}が{victim}をキル"

        if t == "ELITE_MONSTER_KILL":
            killer = champ_from_pid(ev.get("killerId"))
            monster = ev.get("monsterType", "")
            sub = ev.get("monsterSubType", "")

            name_map = {
                "DRAGON": "ドラゴン",
                "BARON_NASHOR": "バロン",
                "RIFTHERALD": "リフトヘラルド",
            }
            m = name_map.get(monster, monster or "オブジェクト")
            if sub:
                m = f"{m}（{sub}）"

            icon = "🐉" if monster == "DRAGON" else "👑"
            return f"{icon} {killer}が{m}を討伐"

        if t == "BUILDING_KILL":
            killer = champ_from_pid(ev.get("killerId"))
            building = ev.get("buildingType", "")
            lane = ev.get("laneType", "")

            if building == "TOWER_BUILDING":
                icon = "🏰"
                b = "タワー"
            elif building == "INHIBITOR_BUILDING":
                icon = "💎"
                b = "インヒビター"
            else:
                icon = "🏗️"
                b = building or "建物"

            lane_map = {
                "TOP_LANE": "トップ",
                "MID_LANE": "ミッド",
                "BOT_LANE": "ボット",
            }
            l = lane_map.get(lane, "")
            suffix = f"（{l}）" if l else ""
            return f"{icon} {killer}が{b}{suffix}を破壊"

        if t == "WARD_PLACED":
            who = champ_from_pid(ev.get("creatorId"))
            return f"👁️ {who}がワードを設置"

        if t == "WARD_KILL":
            who = champ_from_pid(ev.get("killerId"))
            return f"🧹 {who}がワードを破壊"

        return ""

    events = []
    for frame in timeline["info"]["frames"]:
        for ev in frame.get("events", []) or []:
            if ev.get("type") not in ALLOWED_EVENT_TYPES:
                continue

            ts = ev.get("timestamp", 0) or 0

            # どっちチームのイベントか（killer/creator/victimなどから引ける範囲で）
            teamId = None
            for pid_key in ("participantId", "killerId", "creatorId", "victimId"):
                pid = ev.get(pid_key)
                p = get_p(pid)
                if p:
                    teamId = p.get("teamId")
                    break

            user_involved = user_pid is not None and user_pid in [
                ev.get("killerId"), ev.get("victimId"), ev.get("creatorId"), ev.get("participantId")
            ]

            events.append({
                "t": ts,
                "time": fmt_time(ts),
                "type": ev.get("type", ""),
                "teamId": teamId,
                "team": ("味方" if teamId == user_team_id else ("敵" if teamId in (100, 200) else "")),
                "team_en": ("Ally" if teamId == user_team_id else ("Enemy" if teamId in (100, 200) else "")),
                "text": event_to_text(ev),
                "text_en": event_to_text_en(ev),
                "is_user": user_involved,
                "raw": ev,
            })

    # textが空のものは落とす（欠損イベントなど）
    events = [e for e in events if e.get("text")]
    events.sort(key=lambda x: x["t"])

    def html_escape(s):
        return html.escape(str(s), quote=True)

    def table_html(rows, title_key, team_id):
        title_ja = "味方チーム" if title_key == "ally_team" else "敵チーム"
        head = ["POS", "Player", "Champion", "K/D/A", "KDA", "CS", "Gold", "DMG", "Vision", "CC"]
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

    events_json = json.dumps(events, ensure_ascii=False)
    players_json = json.dumps([
        {"champ": r["champ"], "champName": r["champName"], "player": r["player"],
         "k": r["k"], "d": r["d"], "a": r["a"],
         "kda": round(r["kda"], 4), "cc": r["cc"],
         "dmg": r["dmg"], "taken": r["taken"],
         "gold": r["gold"], "cs": r["cs"], "vision": r["vision"],
         "kp": round(r["kp"], 4), "dead_s": r["dead_s"],
         "pid": r["pid"],
         "teamId": r["teamId"], "is_user": r["is_user"]}
        for r in friend_rows + enemy_rows
    ], ensure_ascii=False)

    game_info = match["info"]
    _gv_parts = game_info.get("gameVersion", "0.0").split(".")[:2]
    dd_version = ".".join(_gv_parts) + ".1"
    game_duration = game_info.get("gameDuration", 1) or 1

    # Timeline フレームからチームゴールド差分を抽出
    pid_to_team = {p["participantId"]: p["teamId"] for p in participants}
    gold_frames = []
    for frame in timeline["info"].get("frames", []):
        ts = frame.get("timestamp", 0) // 1000  # ms → 秒
        pf = frame.get("participantFrames", {})
        friend_g = sum(
            pf[str(pid)].get("totalGold", 0)
            for pid in pid_to_team
            if pid_to_team[pid] == friend_team_id and str(pid) in pf
        )
        enemy_g = sum(
            pf[str(pid)].get("totalGold", 0)
            for pid in pid_to_team
            if pid_to_team[pid] != friend_team_id and str(pid) in pf
        )
        gold_frames.append({"t": ts, "diff": friend_g - enemy_g})
    gold_frames_json = json.dumps(gold_frames, ensure_ascii=False)

    meta = (
        f"Mode: {game_info.get('gameMode','')} / "
        f"Duration: {game_info.get('gameDuration',0)//60}:{game_info.get('gameDuration',0)%60:02d} / "
        f"Version: {game_info.get('gameVersion','')}"
    )

    used_files = f"match: {match_path.name} / timeline: {timeline_path.name} / champ: {champ_path.name}"

    html_doc = f"""<!doctype html>
<html lang=\"ja\">
<head>
<meta charset=\"utf-8\"/>
<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"/>
<title>LoL Match Viewer - {html_escape(match['metadata'].get('matchId',''))}</title>
<style>
  :root {{ --bg:#0b0f17; --card:#121a2a; --text:#e9eef8; --muted:#9fb0cf; --line:#26334d;
    --blue:#2f7bf6; --red:#ff4d5a; --pill:#1b2740; }}
  body {{ margin:0; font-family: system-ui, -apple-system, \"Segoe UI\", Roboto, \"Noto Sans JP\", sans-serif; background:var(--bg); color:var(--text); }}
  header {{ padding:16px 18px; border-bottom:1px solid var(--line); position:sticky; top:0; background:rgba(11,15,23,.95); backdrop-filter: blur(6px); z-index:10;}}
  header h1 {{ margin:0; font-size:18px; }}
  header .meta {{ margin-top:6px; color:var(--muted); font-size:12px; }}
  main {{ max-width: 1100px; margin: 0 auto; padding: 16px; display:grid; gap: 12px; }}
  .card {{ background:var(--card); border:1px solid var(--line); border-radius:14px; padding: 12px; }}
  h2 {{ margin: 6px 0 12px; font-size: 15px; }}
  .table-wrap {{ overflow:auto; }}
  table {{ width:100%; border-collapse: collapse; min-width: 860px; }}
  th, td {{ padding: 8px 10px; border-bottom:1px solid var(--line); text-align:left; font-size: 12px; white-space: nowrap; }}
  th {{ position: sticky; top: 0; background: #0f1726; z-index: 1; }}
  tr.user td {{ outline: 1px solid rgba(47,123,246,.35); background: rgba(47,123,246,.08); }}
  .toolbar {{ display:flex; flex-wrap:wrap; gap: 8px; align-items:center; }}
  .toolbar input, .toolbar select {{ background:#0f1726; border:1px solid var(--line); color:var(--text); padding:8px 10px; border-radius:10px; font-size:12px; }}
  .pill {{ display:inline-flex; gap:6px; align-items:center; padding: 3px 8px; border-radius:999px; background:var(--pill); border:1px solid var(--line); font-size: 11px; color: var(--muted); }}
  .pill .dot {{ width:8px; height:8px; border-radius:999px; background: var(--muted); display:inline-block; }}
  .dot.blue {{ background: var(--blue); }}
  .dot.red {{ background: var(--red); }}
  .events {{ display:grid; gap:6px; margin-top: 10px; }}
  .event {{ border:1px solid var(--line); border-radius:12px; padding: 10px; display:flex; gap: 10px; align-items:flex-start; background: rgba(255,255,255,0.02); }}
  .event.friend {{ background: rgba(47,123,246,0.10); }}
  .event.enemy {{ background: rgba(255,77,90,0.10); }}
  .event .time {{ width: 52px; color: var(--muted); font-variant-numeric: tabular-nums; }}
  .event .etype {{ width: 170px; color:var(--muted); }}
  .event .txt {{ flex:1; }}
  .event .team {{ margin-left:auto; }}
  .team.blue {{ color: var(--blue); }}
  .team.red {{ color: var(--red); }}
  .event.user-event {{ outline: 2px solid #f0c040; background: rgba(240,192,64,0.12) !important; }}
  /* ── ビジュアルイベント行 ─────────────────────────────────────── */
  .ev-row {{ display:flex; align-items:center; gap:8px; padding:6px 10px;
    border-radius:12px; border:1px solid var(--line);
    background:rgba(255,255,255,0.02); }}
  .ev-row.friend {{ background:rgba(47,123,246,0.08); }}
  .ev-row.enemy  {{ background:rgba(255,77,90,0.08); }}
  .ev-row.user-event {{ outline:2px solid #f0c040; background:rgba(240,192,64,0.10) !important; }}
  .ev-time {{ width:44px; font-variant-numeric:tabular-nums;
    color:var(--muted); font-size:11px; flex-shrink:0; }}
  .ev-icons {{ display:flex; align-items:center; gap:6px; flex-shrink:0; }}
  .ev-killer-group {{ display:flex; align-items:center; gap:3px; flex-shrink:0; }}
  .ev-assists-col {{ display:flex; flex-direction:column; gap:2px; justify-content:center; }}
  .ev-champ {{ border-radius:50%; object-fit:cover;
    border:1.5px solid rgba(255,255,255,0.2); flex-shrink:0; }}
  .ev-champ.killer {{ width:48px; height:48px; border-width:2px; border-color:#fbbf24; }}
  .ev-champ.victim  {{ width:32px; height:32px; border-color:#ff4d5a; filter:brightness(.72); }}
  .ev-champ.assist  {{ width:24px; height:24px; border-width:1px;
    border-color:rgba(255,255,255,0.28); }}
  .ev-champ.user    {{ border-color:#f0c040; box-shadow:0 0 6px #f0c04088; }}
  .ev-verb {{ font-size:18px; flex-shrink:0; line-height:1; }}
  .ev-label {{ flex:1; font-size:11px; color:var(--muted); white-space:nowrap;
    overflow:hidden; text-overflow:ellipsis; }}
  details {{ margin-top: 6px; }}
  details summary {{ cursor:pointer; color: var(--muted); font-size: 12px; }}
  pre {{ white-space: pre-wrap; word-break: break-word; background:#0f1726; border:1px solid var(--line); padding:10px; border-radius:10px; font-size:11px; color: var(--text); }}
  footer {{ color: var(--muted); font-size: 11px; padding: 0 16px 18px; text-align:center; }}
  #lang-toggle {{ background:var(--pill); border:1px solid var(--line); color:var(--text);
    padding:5px 14px; border-radius:8px; cursor:pointer; font-size:12px; margin-top:8px; }}
  #lang-toggle:hover {{ background:var(--blue); color:#fff; }}
  .charts-wrap {{ display:grid; grid-template-columns:1fr 1fr; gap:12px; }}
  .charts-wrap > .card.chart-full {{ grid-column:1/-1; }}
  @media(max-width:680px) {{ .charts-wrap {{ grid-template-columns:1fr; }}
    .charts-wrap > .card {{ grid-column:1 !important; }} }}
  .chart-label {{ margin:0 0 10px; font-size:14px; font-weight:600;
    letter-spacing:.05em; text-transform:uppercase; color:var(--muted); }}
  canvas {{ display:block; }}
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
    <section class=\"card\"><p class=\"chart-label\" data-i18n=\"chart_radar_ally\">味方チーム — パフォーマンス</p>
      <canvas id=\"chart-radar-friend\"></canvas></section>
    <section class=\"card\"><p class=\"chart-label\" data-i18n=\"chart_radar_enemy\">敵チーム — パフォーマンス</p>
      <canvas id=\"chart-radar-enemy\"></canvas></section>
    <section class=\"card\"><p class=\"chart-label\" data-i18n=\"chart_kp\">キルへの関与率（KP%）</p>
      <canvas id=\"chart-kp\"></canvas></section>
    <section class=\"card\"><p class=\"chart-label\" data-i18n=\"chart_dead\">デス時間（試合時間比% ／ 低いほど良）</p>
      <canvas id=\"chart-dead\"></canvas></section>
    <section class=\"card chart-full\"><p class=\"chart-label\" data-i18n=\"chart_gold_diff\">チームゴールドリード 推移</p>
      <canvas id=\"chart-gold-diff\"></canvas></section>
  </div>

  <section class=\"card\">
    <h2 data-i18n=\"timeline_title\">時系列イベント（キル / オブジェクト / ワード）</h2>
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
      <select id=\"detail\">
        <option value=\"0\" data-i18n=\"detail_hide\">詳細: 非表示</option>
        <option value=\"1\" data-i18n=\"detail_show\">詳細: 表示</option>
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

<script id="dd-version" type="application/json">"{dd_version}"</script>
<script id="game-duration" type="application/json">{game_duration}</script>
<script id="gold-frames" type="application/json">{gold_frames_json}</script>
<script id="players-data" type="application/json">{players_json}</script>
<script id=\"events-data\" type=\"application/json\">{events_json}</script>
<script>
// ── i18n ──────────────────────────────────────────────────────────────────
const I18N = {{
  ja: {{
    ally_team:'味方チーム', enemy_team:'敵チーム',
    chart_kda_breakdown:'KDA 内訳', chart_kda_ratio:'KDA 比率',
    chart_dmg:'ダメージ', chart_gold:'ゴールド', chart_cs:'CS',
    chart_vision:'視界スコア', chart_cc:'CC タイム（秒）',
    chart_scatter:'与ダメ / 被ダメ 分布',
    chart_radar_ally:'味方チーム — パフォーマンス',
    chart_radar_enemy:'敵チーム — パフォーマンス',
    chart_kp:'キルへの関与率（KP%）',
    chart_dead:'デス時間（試合時間比% ／ 低いほど良）',
    chart_gold_diff:'チームゴールドリード 推移',
    q_tank:'タンク', q_fighter:'ファイター', q_support:'サポート', q_carry:'キャリー',
    axis_dmg_dealt:'与ダメージ →', axis_dmg_taken:'← 被ダメージ',
    ally_lead:'▲ 味方リード', enemy_lead:'▼ 敵リード',
    legend_deaths:'Deaths ←', legend_kills:'→ K', legend_assists:'A',
    timeline_title:'時系列イベント（キル / オブジェクト / ワード）',
    search_ph:'検索: 例) キル / ドラゴン / ワード / ルル など',
    team_all:'Team: 全部', team_ally:'味方', team_enemy:'敵',
    type_all:'Type: 全部',
    detail_hide:'詳細: 非表示', detail_show:'詳細: 表示',
    pill_count:'イベント件数',
  }},
  en: {{
    ally_team:'Ally Team', enemy_team:'Enemy Team',
    chart_kda_breakdown:'KDA Breakdown', chart_kda_ratio:'KDA Ratio',
    chart_dmg:'Damage', chart_gold:'Gold', chart_cs:'CS',
    chart_vision:'Vision Score', chart_cc:'CC Time (sec)',
    chart_scatter:'Damage Dealt vs Taken',
    chart_radar_ally:'Ally Team — Performance',
    chart_radar_enemy:'Enemy Team — Performance',
    chart_kp:'Kill Participation (KP%)',
    chart_dead:'Dead Time (% of game, lower is better)',
    chart_gold_diff:'Team Gold Lead Over Time',
    q_tank:'Tank', q_fighter:'Fighter', q_support:'Support', q_carry:'Carry',
    axis_dmg_dealt:'Damage Dealt →', axis_dmg_taken:'← Damage Taken',
    ally_lead:'▲ Ally Lead', enemy_lead:'▼ Enemy Lead',
    legend_deaths:'Deaths ←', legend_kills:'→ K', legend_assists:'A',
    timeline_title:'Event Timeline (Kills / Objectives / Wards)',
    search_ph:'Search: e.g. kill / dragon / ward / champion name',
    team_all:'Team: All', team_ally:'Ally', team_enemy:'Enemy',
    type_all:'Type: All',
    detail_hide:'Detail: Hide', detail_show:'Detail: Show',
    pill_count:'Events',
  }},
}};
let currentLang = 'ja';
function t(key) {{ return (I18N[currentLang] || I18N.ja)[key] || key; }}

function applyLang(lang) {{
  currentLang = lang;
  document.querySelectorAll('[data-i18n]').forEach(el => {{
    const key = el.getAttribute('data-i18n');
    const teamId = el.getAttribute('data-i18n-team');
    if (teamId !== null) {{
      const suffix = lang === 'ja' ? ` — 一覧（team ${{teamId}}）` : ` — team ${{teamId}}`;
      el.textContent = t(key) + suffix;
    }} else {{
      el.textContent = t(key);
    }}
  }});
  document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {{
    el.placeholder = t(el.getAttribute('data-i18n-placeholder'));
  }});
  document.querySelectorAll('[data-champ-en]').forEach(el => {{
    if (lang === 'en') {{
      if (!el.getAttribute('data-champ-ja')) el.setAttribute('data-champ-ja', el.textContent);
      el.textContent = el.getAttribute('data-champ-en');
    }} else {{
      const ja = el.getAttribute('data-champ-ja');
      if (ja) el.textContent = ja;
    }}
  }});
  const btn = document.getElementById('lang-toggle');
  if (btn) btn.textContent = lang === 'ja' ? '🌐 EN' : '🌐 JA';
  if (window._renderAll) window._renderAll();
  render();
}}
function toggleLang() {{ applyLang(currentLang === 'ja' ? 'en' : 'ja'); }}

// ── event data ────────────────────────────────────────────────────────────
const events     = JSON.parse(document.getElementById('events-data').textContent);
const userTeamId = {friend_team_id};
const _players   = JSON.parse(document.getElementById('players-data').textContent);
const _DD_VER    = JSON.parse(document.getElementById('dd-version').textContent);

// participantId → player 逆引きマップ（イベントアイコン用）
const pid2player = {{}};
_players.forEach(p => {{ if (p.pid) pid2player[p.pid] = p; }});

// champion <img> タグ生成
function champImg(pid, cls) {{
  const p = pid2player[pid];
  if (!p || !p.champName) return '';
  const userCls = p.is_user ? ' user' : '';
  const src = `https://ddragon.leagueoflegends.com/cdn/${{_DD_VER}}/img/champion/${{p.champName}}.png`;
  return `<img class="ev-champ ${{cls}}${{userCls}}" src="${{src}}" title="${{p.champ}}" loading="lazy">`;
}}

// キラー + アシスト縦並びグループ
function killerGroupHtml(killerPid, assistPids) {{
  const killer = champImg(killerPid, 'killer');
  const assistCol = (assistPids && assistPids.length > 0)
    ? `<div class="ev-assists-col">${{assistPids.map(pid => champImg(pid, 'assist')).join('')}}</div>`
    : '';
  return `<div class="ev-killer-group">${{killer}}${{assistCol}}</div>`;
}}

// イベント行HTML生成
function buildEventHtml(e, showDetail) {{
  const r = e.raw || {{}};
  const sideClass = (e.teamId === userTeamId) ? 'friend' : (e.teamId ? 'enemy' : '');
  const userClass  = e.is_user ? ' user-event' : '';
  let iconsHtml = '';
  const labelText = currentLang === 'ja' ? e.text : (e.text_en || e.text);

  if (e.type === 'CHAMPION_KILL') {{
    iconsHtml = killerGroupHtml(r.killerId, r.assistingParticipantIds) +
                '<span class="ev-verb">⚔️</span>' +
                champImg(r.victimId, 'victim');
  }} else if (e.type === 'BUILDING_KILL') {{
    const icon = (r.buildingType === 'INHIBITOR_BUILDING') ? '💎' : '🏰';
    iconsHtml = killerGroupHtml(r.killerId, r.assistingParticipantIds) +
                `<span class="ev-verb">${{icon}}</span>`;
  }} else if (e.type === 'ELITE_MONSTER_KILL') {{
    const icon = r.monsterType === 'BARON_NASHOR' ? '🐗' :
                 r.monsterType === 'DRAGON'       ? '🐉' : '👾';
    iconsHtml = champImg(r.killerId, 'killer') + `<span class="ev-verb">${{icon}}</span>`;
  }}

  let detailHtml = '';
  if (showDetail) {{
    detailHtml = `<details style="font-size:11px;padding:2px 8px 6px;flex-basis:100%">` +
                 `<summary>raw event (JSON)</summary>` +
                 `<pre style="overflow:auto;max-height:200px">${{escapeHtml(JSON.stringify(e.raw, null, 2))}}</pre>` +
                 `</details>`;
  }}

  return `<div class="ev-row ${{sideClass}}${{userClass}}">` +
         `<div class="ev-time">${{e.time}}</div>` +
         `<div class="ev-icons">${{iconsHtml}}</div>` +
         `<div class="ev-label">${{escapeHtml(labelText)}}</div>` +
         detailHtml +
         `</div>`;
}}

const $q = document.getElementById('q');
const $team = document.getElementById('team');
const $type = document.getElementById('type');
const $detail = document.getElementById('detail');
const $events = document.getElementById('events');
const $count = document.getElementById('count');

function uniq(arr) {{
  return Array.from(new Set(arr)).filter(Boolean).sort();
}}

function buildTypeOptions() {{
  const types = uniq(events.map(e => e.type));
  for (const t of types) {{
    const opt = document.createElement('option');
    opt.value = t;
    opt.textContent = t;
    $type.appendChild(opt);
  }}
}}

function escapeHtml(str) {{
  return String(str).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;');
}}

function render() {{
  const q = ($q.value || '').toLowerCase();
  const team = $team.value;
  const type = $type.value;
  const showDetail = $detail.value === "1";

  const filtered = events.filter(e => {{
    if (team && String(e.teamId) !== team) return false;
    if (type && e.type !== type) return false;
    if (q) {{
      const hay = (e.time + " " + (e.team||"") + " " + (e.team_en||"") + " " + e.type + " " + e.text + " " + (e.text_en||"")).toLowerCase();
      if (!hay.includes(q)) return false;
    }}
    return true;
  }});

  $count.textContent = filtered.length;
  $events.innerHTML = "";

  for (const e of filtered) {{
    $events.insertAdjacentHTML('beforeend', buildEventHtml(e, showDetail));
  }}
}}

[$q, $team, $type, $detail].forEach(el => el.addEventListener('input', render));
[$team, $type, $detail].forEach(el => el.addEventListener('change', render));

buildTypeOptions();
render();
</script>
<script>
(function() {{
  const players      = JSON.parse(document.getElementById('players-data').textContent);
  const friendTeamId = {friend_team_id};
  const DD_VER       = JSON.parse(document.getElementById('dd-version').textContent);
  const gameDuration = JSON.parse(document.getElementById('game-duration').textContent);
  const goldFrames   = JSON.parse(document.getElementById('gold-frames').textContent);

  // ── roundRect polyfill ────────────────────────────────────────────────────
  if (!CanvasRenderingContext2D.prototype.roundRect) {{
    CanvasRenderingContext2D.prototype.roundRect = function(x, y, w, h, r) {{
      r = Math.min(typeof r === 'number' ? r : (r[0] || 0), w / 2, h / 2);
      this.beginPath();
      this.moveTo(x + r, y);
      this.lineTo(x + w - r, y);
      this.quadraticCurveTo(x + w, y, x + w, y + r);
      this.lineTo(x + w, y + h - r);
      this.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
      this.lineTo(x + r, y + h);
      this.quadraticCurveTo(x, y + h, x, y + h - r);
      this.lineTo(x, y + r);
      this.quadraticCurveTo(x, y, x + r, y);
      this.closePath();
      return this;
    }};
  }}

  // ── ユーティリティ ────────────────────────────────────────────────────────
  function setupCanvas(canvas, w, h) {{
    const dpr = window.devicePixelRatio || 1;
    canvas.width = Math.round(w * dpr);
    canvas.height = Math.round(h * dpr);
    canvas.style.width = w + 'px';
    canvas.style.height = h + 'px';
    const ctx = canvas.getContext('2d');
    ctx.scale(dpr, dpr);
    return ctx;
  }}

  function fmtNum(n) {{
    return n >= 10000 ? (n / 1000).toFixed(1) + 'k' : String(n);
  }}

  const COL = {{
    text: '#9fb0cf', muted: 'rgba(158,176,207,0.45)', grid: 'rgba(255,255,255,0.05)',
    user: '#f0c040',
    kill: '#fbbf24', death: '#ff4d5a', assist: '#a78bfa',
    friendA: '#1245a8', friendB: '#3b8ef0',
    enemyA:  '#8b1a24', enemyB:  '#ff4d5a',
    tealA:   '#064a3c', tealB:   '#06d6a0',
    orangeA: '#4a2a00', orangeB: '#ff9500',
  }};

  const ROW = 36, LABEL_W = 128;

  // ── チャンピオンアイコン プリロード ───────────────────────────────────────
  const champIcons = {{}};
  let iconsReady = false;
  const _names = [...new Set(players.map(p => p.champName).filter(Boolean))];
  let _loaded = 0;
  function _onIconLoad() {{
    if (++_loaded === _names.length) {{ iconsReady = true; renderAll(); }}
  }}
  _names.forEach(name => {{
    const img = new Image();
    img.crossOrigin = 'anonymous';
    img.onload  = () => {{ champIcons[name] = img; _onIconLoad(); }};
    img.onerror = _onIconLoad;
    img.src = `https://ddragon.leagueoflegends.com/cdn/${{DD_VER}}/img/champion/${{name}}.png`;
  }});
  if (_names.length === 0) iconsReady = true;

  // ── 丸アイコン描画 ────────────────────────────────────────────────────────
  function drawCircleIcon(ctx, champName, cx, cy, r) {{
    ctx.save();
    ctx.beginPath(); ctx.arc(cx, cy, r, 0, Math.PI * 2); ctx.clip();
    const img = champIcons[champName];
    if (img) {{ ctx.drawImage(img, cx - r, cy - r, r * 2, r * 2); }}
    else      {{ ctx.fill(); }}
    ctx.restore();
  }}

  function playerColor(p, isFriend) {{
    return p.is_user ? COL.user : (isFriend ? '#c8d8f0' : '#f0b8bc');
  }}

  function drawLabel(ctx, p, x, y, h) {{
    const isFriend = p.teamId === friendTeamId;
    const iconR = 11;
    const iconCx = x - iconR - 6;
    const iconCy = y + h / 2;
    if (iconsReady) {{
      ctx.fillStyle = isFriend ? '#1a3a6a' : '#5a1a20';
      drawCircleIcon(ctx, p.champName, iconCx, iconCy, iconR);
      // アイコン枠
      ctx.strokeStyle = p.is_user ? COL.user : (isFriend ? '#3b8ef0' : '#ff4d5a');
      ctx.lineWidth = p.is_user ? 2 : 1;
      ctx.beginPath(); ctx.arc(iconCx, iconCy, iconR, 0, Math.PI * 2); ctx.stroke();
    }}
    ctx.fillStyle = playerColor(p, isFriend);
    ctx.font = (p.is_user ? '600 ' : '') + '10px system-ui,sans-serif';
    ctx.textAlign = 'right';
    ctx.fillText(p.champ, iconCx - iconR - 4, iconCy + 4);
  }}

  // ── 汎用 横棒チャート ─────────────────────────────────────────────────────
  function drawHBar(canvas, sorted, key, fmt, gradFriend, gradEnemy) {{
    const W = canvas.parentElement.clientWidth - 24;
    const PAD = {{ t: 8, r: 56, b: 8, l: LABEL_W }};
    const H = PAD.t + sorted.length * ROW + PAD.b;
    const ctx = setupCanvas(canvas, W, H);
    const chartW = W - PAD.l - PAD.r;
    const maxVal = Math.max(...sorted.map(p => p[key]), 1);

    sorted.forEach((p, i) => {{
      const y = PAD.t + i * ROW;
      const bY = y + 8, bH = ROW - 14;
      const bw = Math.max((p[key] / maxVal) * chartW, p[key] > 0 ? 3 : 0);
      const isFriend = p.teamId === friendTeamId;

      drawLabel(ctx, p, PAD.l, bY, bH);

      // BG track
      ctx.fillStyle = 'rgba(255,255,255,0.03)';
      ctx.beginPath(); ctx.roundRect(PAD.l, bY, chartW, bH, 4); ctx.fill();

      if (bw > 0) {{
        const [cA, cB] = isFriend ? gradFriend : gradEnemy;
        const grad = ctx.createLinearGradient(PAD.l, 0, PAD.l + bw, 0);
        grad.addColorStop(0, cA); grad.addColorStop(1, cB);
        ctx.fillStyle = grad;
        ctx.beginPath(); ctx.roundRect(PAD.l, bY, bw, bH, 4); ctx.fill();

        if (p.is_user) {{
          ctx.shadowColor = COL.user; ctx.shadowBlur = 8;
          ctx.fillStyle = 'rgba(240,192,64,0.15)';
          ctx.beginPath(); ctx.roundRect(PAD.l, bY, bw, bH, 4); ctx.fill();
          ctx.shadowBlur = 0;
        }}
      }}

      ctx.fillStyle = COL.text;
      ctx.font = '11px system-ui,sans-serif';
      ctx.textAlign = 'left';
      ctx.fillText(fmt(p[key]), PAD.l + bw + 6, bY + bH / 2 + 4);
    }});
  }}

  // ── ロリポップチャート（単一値比較）────────────────────────────────────────
  function drawLollipop(canvas, sorted, key, fmt, gradFriend, gradEnemy) {{
    const W = canvas.parentElement.clientWidth - 24;
    const PAD = {{ t: 8, r: 64, b: 8, l: LABEL_W }};
    const H = PAD.t + sorted.length * ROW + PAD.b;
    const ctx = setupCanvas(canvas, W, H);
    const chartW = W - PAD.l - PAD.r;
    const maxVal = Math.max(...sorted.map(p => p[key]), 1);

    sorted.forEach((p, i) => {{
      const y    = PAD.t + i * ROW;
      const midY = y + ROW / 2;
      const isFriend = p.teamId === friendTeamId;
      const stemX = PAD.l + Math.max((p[key] / maxVal) * chartW, 0);
      const dotR  = p.is_user ? 12 : 10;

      drawLabel(ctx, p, PAD.l, y + 7, ROW - 14);

      // トラック（全幅・薄いライン）
      ctx.strokeStyle = 'rgba(255,255,255,0.05)';
      ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(PAD.l, midY); ctx.lineTo(PAD.l + chartW, midY); ctx.stroke();

      if (p[key] > 0) {{
        // ステム（グラデーションライン）
        const [cA, cB] = isFriend ? gradFriend : gradEnemy;
        if (p.is_user) {{
          ctx.strokeStyle = COL.user;
          ctx.lineWidth = 2;
        }} else {{
          const grad = ctx.createLinearGradient(PAD.l, 0, stemX, 0);
          grad.addColorStop(0, hexRgba(cA, 0.3));
          grad.addColorStop(1, hexRgba(cB, 0.9));
          ctx.strokeStyle = grad;
          ctx.lineWidth = 1.5;
        }}
        ctx.beginPath(); ctx.moveTo(PAD.l, midY); ctx.lineTo(stemX, midY); ctx.stroke();

        // ドット
        if (p.is_user) {{ ctx.shadowColor = COL.user; ctx.shadowBlur = 10; }}
        ctx.fillStyle = p.is_user ? COL.user : (isFriend ? gradFriend[1] : gradEnemy[1]);
        ctx.beginPath(); ctx.arc(stemX, midY, dotR, 0, Math.PI * 2); ctx.fill();
        ctx.shadowBlur = 0;

        // ドット外枠
        ctx.strokeStyle = p.is_user ? 'rgba(255,255,255,0.8)' : 'rgba(255,255,255,0.18)';
        ctx.lineWidth = p.is_user ? 1.5 : 1;
        ctx.beginPath(); ctx.arc(stemX, midY, dotR, 0, Math.PI * 2); ctx.stroke();
      }}

      // 値ラベル
      ctx.fillStyle = p.is_user ? COL.user : COL.text;
      ctx.font = (p.is_user ? '600 ' : '') + '11px system-ui,sans-serif';
      ctx.textAlign = 'left';
      ctx.fillText(fmt(p[key]), stemX + dotR + 6, midY + 4);
    }});
  }}

  // ── KDA 内訳（ダイバージング横棒: ← Deaths | K + A →）───────────────────
  function drawKDABreakdown(canvas) {{
    const W = canvas.parentElement.clientWidth - 24;
    const PAD = {{ t: 28, r: 16, b: 8, l: LABEL_W }};
    const H = PAD.t + players.length * ROW + PAD.b;
    const ctx = setupCanvas(canvas, W, H);
    const chartW = W - PAD.l - PAD.r;

    // maxD : maxKA の比率で左右幅を割り振り → 1:1スケール維持 + 最多デスが左端に届く
    const maxD  = Math.max(...players.map(p => p.d), 1);
    const maxKA = Math.max(...players.map(p => p.k + p.a), 1);
    const pixPerUnit = (chartW - 2) / (maxD + maxKA);
    const leftW  = Math.round(maxD  * pixPerUnit);  // デス側の幅
    const rightW = chartW - 2 - leftW;              // K+A側の幅
    const cX     = PAD.l + leftW;                   // ベースライン X

    // 凡例: 左側 "Deaths ←" / 右側 "→ K  A"
    ctx.fillStyle = COL.death;
    ctx.beginPath(); ctx.roundRect(cX - 80, 6, 12, 10, 3); ctx.fill();
    ctx.fillStyle = COL.muted; ctx.font = '10px system-ui,sans-serif';
    ctx.textAlign = 'right';
    ctx.fillText(t('legend_deaths'), cX - 4, 15);

    [[COL.kill, t('legend_kills')], [COL.assist, t('legend_assists')]].forEach(([c, lbl], i) => {{
      const lx = cX + 4 + i * 44;
      ctx.fillStyle = c;
      ctx.beginPath(); ctx.roundRect(lx, 6, 12, 10, 3); ctx.fill();
      ctx.fillStyle = COL.muted; ctx.textAlign = 'left';
      ctx.fillText(lbl, lx + 16, 15);
    }});

    // 中心線（縦）
    ctx.strokeStyle = 'rgba(255,255,255,0.18)';
    ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(cX, PAD.t - 4); ctx.lineTo(cX, H - PAD.b); ctx.stroke();

    players.forEach((p, i) => {{
      const y = PAD.t + i * ROW;
      const bY = y + 8, bH = ROW - 14;

      // チーム区切り線
      if (i > 0 && players[i - 1].teamId !== p.teamId) {{
        ctx.strokeStyle = 'rgba(255,255,255,0.1)';
        ctx.lineWidth = 1;
        ctx.beginPath(); ctx.moveTo(PAD.l, y - 2); ctx.lineTo(W - PAD.r, y - 2); ctx.stroke();
      }}

      drawLabel(ctx, p, PAD.l, bY, bH);

      // ユーザー行 背景ハイライト
      if (p.is_user) {{
        ctx.fillStyle = 'rgba(240,192,64,0.05)';
        ctx.fillRect(PAD.l, bY - 3, chartW, bH + 6);
      }}

      // BG トラック（左・右）
      ctx.fillStyle = 'rgba(255,255,255,0.03)';
      ctx.beginPath(); ctx.roundRect(PAD.l, bY, leftW,   bH, [4, 0, 0, 4]); ctx.fill();
      ctx.beginPath(); ctx.roundRect(cX + 1, bY, rightW, bH, [0, 4, 4, 0]); ctx.fill();

      // Deaths（左向き）
      const dW = Math.round(p.d * pixPerUnit);
      if (dW > 0) {{
        ctx.fillStyle = COL.death;
        ctx.beginPath(); ctx.roundRect(cX - dW, bY, dW, bH, [4, 0, 0, 4]); ctx.fill();
        if (dW > 16) {{
          ctx.fillStyle = 'rgba(0,0,0,0.7)';
          ctx.font = 'bold 10px system-ui,sans-serif';
          ctx.textAlign = 'center';
          ctx.fillText(p.d, cX - dW / 2, bY + bH / 2 + 4);
        }}
      }}

      // Kills + Assists（右向き・積み上げ）
      const kW  = Math.round(p.k * pixPerUnit);
      const aW  = Math.round(p.a * pixPerUnit);
      const kaW = Math.min(kW + aW, rightW);
      if (kaW > 0) {{
        ctx.save();
        ctx.beginPath(); ctx.roundRect(cX + 1, bY, kaW, bH, [0, 4, 4, 0]); ctx.clip();
        if (kW > 0) {{
          ctx.fillStyle = COL.kill;
          ctx.fillRect(cX + 1, bY, kW, bH);
          if (kW > 16) {{
            ctx.fillStyle = 'rgba(0,0,0,0.7)';
            ctx.font = 'bold 10px system-ui,sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText(p.k, cX + 1 + kW / 2, bY + bH / 2 + 4);
          }}
        }}
        if (aW > 0) {{
          ctx.fillStyle = COL.assist;
          ctx.fillRect(cX + 1 + kW, bY, aW, bH);
          if (aW > 16) {{
            ctx.fillStyle = 'rgba(0,0,0,0.7)';
            ctx.font = 'bold 10px system-ui,sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText(p.a, cX + 1 + kW + aW / 2, bY + bH / 2 + 4);
          }}
        }}
        ctx.restore();
      }}
    }});
  }}

  // ── 散布図（与ダメ vs 被ダメ）────────────────────────────────────────────
  function drawScatter(canvas) {{
    const W = canvas.parentElement.clientWidth - 24;
    const PAD = {{ t: 20, r: 30, b: 48, l: 64 }};
    const H = 340;
    const ctx = setupCanvas(canvas, W, H);
    const chartW = W - PAD.l - PAD.r;
    const chartH = H - PAD.t - PAD.b;

    const maxDmg   = Math.max(...players.map(p => p.dmg),   1);
    const maxTaken = Math.max(...players.map(p => p.taken),  1);
    const midDmg   = maxDmg   / 2;
    const midTaken = maxTaken / 2;

    // グリッド
    ctx.strokeStyle = COL.grid;
    ctx.lineWidth = 1;
    [0.25, 0.5, 0.75, 1].forEach(f => {{
      const gx = PAD.l + chartW * f;
      ctx.beginPath(); ctx.moveTo(gx, PAD.t); ctx.lineTo(gx, PAD.t + chartH); ctx.stroke();
      const gy = PAD.t + chartH * (1 - f);
      ctx.beginPath(); ctx.moveTo(PAD.l, gy); ctx.lineTo(PAD.l + chartW, gy); ctx.stroke();
    }});

    // 中央値十字（薄め）
    ctx.strokeStyle = 'rgba(255,255,255,0.12)';
    ctx.lineWidth = 1.5;
    ctx.setLineDash([4, 4]);
    const midX = PAD.l + (midDmg / maxDmg) * chartW;
    const midY = PAD.t + chartH * (1 - midTaken / maxTaken);
    ctx.beginPath(); ctx.moveTo(midX, PAD.t); ctx.lineTo(midX, PAD.t + chartH); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(PAD.l, midY); ctx.lineTo(PAD.l + chartW, midY); ctx.stroke();
    ctx.setLineDash([]);

    // 象限ラベル
    const qlabels = [
      [PAD.l + 6, PAD.t + 14, t('q_tank'), 'rgba(255,77,90,0.5)'],
      [PAD.l + chartW - 80, PAD.t + 14, t('q_fighter'), 'rgba(251,191,36,0.5)'],
      [PAD.l + 6, PAD.t + chartH - 6, t('q_support'), 'rgba(158,176,207,0.4)'],
      [PAD.l + chartW - 68, PAD.t + chartH - 6, t('q_carry'), 'rgba(47,123,246,0.6)'],
    ];
    qlabels.forEach(([qx, qy, txt, c]) => {{
      ctx.fillStyle = c;
      ctx.font = '600 10px system-ui,sans-serif';
      ctx.textAlign = 'left';
      ctx.fillText(txt, qx, qy);
    }});

    // 軸ラベル
    ctx.fillStyle = COL.muted;
    ctx.font = '10px system-ui,sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(t('axis_dmg_dealt'), PAD.l + chartW / 2, H - 8);
    ctx.save();
    ctx.translate(14, PAD.t + chartH / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.fillText(t('axis_dmg_taken'), 0, 0);
    ctx.restore();

    // 軸目盛
    [0, 0.5, 1].forEach(f => {{
      const gx = PAD.l + chartW * f;
      ctx.fillStyle = COL.muted;
      ctx.font = '9px system-ui,sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(fmtNum(Math.round(maxDmg * f)), gx, PAD.t + chartH + 14);
      const gy = PAD.t + chartH * (1 - f);
      ctx.textAlign = 'right';
      ctx.fillText(fmtNum(Math.round(maxTaken * f)), PAD.l - 5, gy + 4);
    }});

    // ドット描画（自分以外先に描いて、自分を最前面に）
    const sorted = [...players].sort((a, b) => a.is_user - b.is_user);
    sorted.forEach(p => {{
      const isFriend = p.teamId === friendTeamId;
      const cx = PAD.l + (p.dmg / maxDmg) * chartW;
      const cy = PAD.t + chartH * (1 - p.taken / maxTaken);
      const r = p.is_user ? 10 : 8;

      // グロー（自プレイヤー）— 光輪を先に描いてからアイコン
      if (p.is_user) {{
        ctx.shadowColor = COL.user; ctx.shadowBlur = 14;
        ctx.fillStyle = COL.user;
        ctx.beginPath(); ctx.arc(cx, cy, r + 1, 0, Math.PI * 2); ctx.fill();
        ctx.shadowBlur = 0;
      }}

      // アイコン（フォールバック: 塗り円）
      ctx.fillStyle = p.is_user ? COL.user : (isFriend ? '#2f7bf6' : '#ff4d5a');
      drawCircleIcon(ctx, p.champName, cx, cy, r);

      // 枠
      ctx.strokeStyle = p.is_user ? COL.user : (isFriend ? '#3b8ef0' : '#ff4d5a');
      ctx.lineWidth = p.is_user ? 2.5 : 1;
      ctx.beginPath(); ctx.arc(cx, cy, r, 0, Math.PI * 2); ctx.stroke();

      // ラベル
      ctx.fillStyle = p.is_user ? COL.user : COL.text;
      ctx.font = (p.is_user ? '600 ' : '') + '10px system-ui,sans-serif';
      ctx.textAlign = 'left';
      ctx.fillText(p.champ, cx + r + 4, cy + 4);
    }});
  }}

  // ── レーダーチャート ──────────────────────────────────────────────────────
  function hexRgba(hex, a) {{
    const n = parseInt(hex.replace('#', ''), 16);
    return `rgba(${{n >> 16}},${{(n >> 8) & 255}},${{n & 255}},${{a}})`;
  }}

  // --- レーダー インタラクション ヘルパー ---
  const _radarState = new Map();
  const _RADAR_KEYS  = ['kda','dmg','gold','cs','vision','cc'];
  const _LEGEND_H    = 60;

  function _radarGeom(canvas) {{
    const W      = canvas.parentElement.clientWidth - 24;
    const H      = 360;
    const cx     = W / 2;
    const maxR   = Math.min(W / 2 - 40, (H - _LEGEND_H - 20) / 2 - 20);
    const radius = Math.max(maxR, 60);
    const radarCy = _LEGEND_H / 2 + radius + 24;
    const N       = _RADAR_KEYS.length;
    const angles  = Array.from({{length: N}}, (_, i) => Math.PI * 2 * i / N - Math.PI / 2);
    return {{ W, H, cx, radarCy, radius, angles }};
  }}

  function _radarPolyPts(p, cx, radarCy, radius, angles, gMax) {{
    return _RADAR_KEYS.map((key, i) => {{
      const val = Math.min((p[key] || 0) / gMax[key], 1);
      return [cx + radius * val * Math.cos(angles[i]),
              radarCy + radius * val * Math.sin(angles[i])];
    }});
  }}

  function _ptInPoly(px, py, poly) {{
    let inside = false;
    for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {{
      const [xi, yi] = poly[i], [xj, yj] = poly[j];
      if (((yi > py) !== (yj > py)) && px < (xj - xi) * (py - yi) / (yj - yi) + xi)
        inside = !inside;
    }}
    return inside;
  }}

  function _radarLegItems(canvas, n) {{
    const {{ W, H }} = _radarGeom(canvas);
    const legY = H - _LEGEND_H + 6;
    const colW = Math.floor(W / 3);
    return Array.from({{length: n}}, (_, pi) => ({{
      iconR: 9,
      iconCx: (pi % 3) * colW + 8 + 9,
      iconCy: legY + Math.floor(pi / 3) * 24 + 9,
    }}));
  }}

  function _redrawRadar(canvas) {{
    const s = _radarState.get(canvas);
    if (s) drawRadar(canvas, s.tp, s.ap);
  }}

  function _setupRadarEvents(canvas) {{
    function getHit(mx, my, s) {{
      const items = _radarLegItems(canvas, s.tp.length);
      for (let pi = 0; pi < items.length; pi++) {{
        const {{ iconCx, iconCy, iconR }} = items[pi];
        if (Math.hypot(mx - iconCx, my - iconCy) <= iconR + 10) return pi;
      }}
      const g = _radarGeom(canvas);
      const gMax = {{}};
      _RADAR_KEYS.forEach(k => {{
        gMax[k] = Math.max(...s.ap.map(p => p[k] || 0), 1);
      }});
      for (let pi = s.tp.length - 1; pi >= 0; pi--) {{
        const poly = _radarPolyPts(s.tp[pi], g.cx, g.radarCy, g.radius, g.angles, gMax);
        if (_ptInPoly(mx, my, poly)) return pi;
      }}
      return null;
    }}

    canvas.addEventListener('mousemove', e => {{
      const s = _radarState.get(canvas);
      if (!s) return;
      const r = canvas.getBoundingClientRect();
      const newH = s.fi !== null ? null : getHit(e.clientX - r.left, e.clientY - r.top, s);
      canvas.style.cursor = (newH !== null || s.fi !== null) ? 'pointer' : 'default';
      if (newH !== s.hi) {{ s.hi = newH; _redrawRadar(canvas); }}
    }});

    canvas.addEventListener('mouseleave', () => {{
      const s = _radarState.get(canvas);
      if (s && s.hi !== null) {{ s.hi = null; _redrawRadar(canvas); }}
      canvas.style.cursor = 'default';
    }});

    function handleClick(mx, my) {{
      const s = _radarState.get(canvas);
      if (!s) return;
      const hi = getHit(mx, my, s);
      if (hi !== null) {{
        s.fi = s.fi === hi ? null : hi;
        s.hi = null;
        canvas.style.cursor = 'pointer';
        _redrawRadar(canvas);
      }}
    }}

    canvas.addEventListener('click', e => {{
      const r = canvas.getBoundingClientRect();
      handleClick(e.clientX - r.left, e.clientY - r.top);
    }});

    canvas.addEventListener('touchstart', e => {{
      const s = _radarState.get(canvas);
      if (!s) return;
      const r   = canvas.getBoundingClientRect();
      const t   = e.touches[0];
      const hi  = getHit(t.clientX - r.left, t.clientY - r.top, s);
      if (hi !== null) {{
        e.preventDefault();
        s.fi = s.fi === hi ? null : hi;
        _redrawRadar(canvas);
      }}
    }}, {{ passive: false }});
  }}

  function drawRadar(canvas, teamPlayers, allPlayers) {{
    // state 初期化（初回のみ event listener セットアップ）
    if (!_radarState.has(canvas)) {{
      _radarState.set(canvas, {{ tp: null, ap: null, fi: null, hi: null }});
      _setupRadarEvents(canvas);
    }}
    const state = _radarState.get(canvas);
    state.tp = teamPlayers;
    state.ap = allPlayers;
    const activeIdx = state.fi !== null ? state.fi : state.hi;  // focus > hover

    const METRICS = [
      {{ key: 'kda',    label: 'KDA'    }},
      {{ key: 'dmg',    label: 'DMG'    }},
      {{ key: 'gold',   label: 'Gold'   }},
      {{ key: 'cs',     label: 'CS'     }},
      {{ key: 'vision', label: 'Vision' }},
      {{ key: 'cc',     label: 'CC'     }},
    ];
    const N = METRICS.length;
    const W = canvas.parentElement.clientWidth - 24;
    const H = 360;
    const ctx = setupCanvas(canvas, W, H);
    const {{ cx, radarCy, radius, angles }} = _radarGeom(canvas);

    const isFriendTeam = teamPlayers.length > 0 && teamPlayers[0].teamId === friendTeamId;
    const TEAM_COLORS = isFriendTeam
      ? ['#60b4ff', '#3b8ef0', '#1a6fd4', '#0d4aaa', '#082e7a']
      : ['#ff8080', '#ff4d5a', '#e02035', '#b01025', '#7a0015'];

    const gMax = {{}};
    METRICS.forEach(m => {{
      gMax[m.key] = Math.max(...allPlayers.map(p => p[m.key] || 0), 1);
    }});

    // グリッド同心多角形
    [0.25, 0.5, 0.75, 1.0].forEach(f => {{
      ctx.beginPath();
      angles.forEach((a, i) => {{
        const gx = cx + radius * f * Math.cos(a);
        const gy = radarCy + radius * f * Math.sin(a);
        i === 0 ? ctx.moveTo(gx, gy) : ctx.lineTo(gx, gy);
      }});
      ctx.closePath();
      ctx.strokeStyle = COL.grid; ctx.lineWidth = 1; ctx.stroke();
    }});

    // 軸線 + ラベル
    angles.forEach((a, i) => {{
      const ex = cx + radius * Math.cos(a), ey = radarCy + radius * Math.sin(a);
      ctx.strokeStyle = COL.grid; ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(cx, radarCy); ctx.lineTo(ex, ey); ctx.stroke();
      const lx = cx + (radius + 18) * Math.cos(a);
      const ly = radarCy + (radius + 18) * Math.sin(a);
      const cosA = Math.cos(a), sinA = Math.sin(a);
      ctx.fillStyle = COL.muted; ctx.font = '10px system-ui,sans-serif';
      ctx.textAlign    = Math.abs(cosA) < 0.15 ? 'center' : cosA > 0 ? 'left' : 'right';
      ctx.textBaseline = Math.abs(sinA) < 0.15 ? 'middle' : sinA > 0 ? 'top'  : 'bottom';
      ctx.fillText(METRICS[i].label, lx, ly);
      ctx.textBaseline = 'alphabetic';
    }});

    // ポリゴン（ユーザーを最前面）
    [...teamPlayers].sort((a, b) => a.is_user - b.is_user).forEach(p => {{
      const origIdx  = teamPlayers.indexOf(p);
      const isUser   = p.is_user;
      const isActive = activeIdx === null || origIdx === activeIdx;
      const color    = isUser ? COL.user : TEAM_COLORS[origIdx % TEAM_COLORS.length];
      const pts = METRICS.map((m, i) => {{
        const val = Math.min((p[m.key] || 0) / gMax[m.key], 1);
        return [cx + radius * val * Math.cos(angles[i]),
                radarCy + radius * val * Math.sin(angles[i])];
      }});

      // 塗り
      ctx.beginPath();
      pts.forEach(([px, py], i) => i === 0 ? ctx.moveTo(px, py) : ctx.lineTo(px, py));
      ctx.closePath();
      ctx.fillStyle = hexRgba(color, isActive ? 0.18 : 0.03);
      ctx.fill();

      // ライン
      if (isUser && isActive) {{ ctx.shadowColor = COL.user; ctx.shadowBlur = 10; }}
      ctx.strokeStyle = isActive ? color : hexRgba(color, 0.18);
      ctx.lineWidth = isActive ? (isUser ? 2.5 : 2.0) : 0.8;
      ctx.beginPath();
      pts.forEach(([px, py], i) => i === 0 ? ctx.moveTo(px, py) : ctx.lineTo(px, py));
      ctx.closePath();
      ctx.stroke();
      ctx.shadowBlur = 0;
    }});

    // 凡例（下部・クリック可）
    const legY = H - _LEGEND_H + 6;
    const colW = Math.floor(W / 3);
    teamPlayers.forEach((p, pi) => {{
      const lx   = (pi % 3) * colW + 8;
      const ly   = legY + Math.floor(pi / 3) * 24;
      const isUser   = p.is_user;
      const isActive = activeIdx === null || pi === activeIdx;
      const color    = isUser ? COL.user : TEAM_COLORS[pi % TEAM_COLORS.length];
      const iconR = 9, iconCx = lx + iconR, iconCy = ly + iconR;

      ctx.globalAlpha = isActive ? 1 : 0.3;
      ctx.fillStyle = isFriendTeam ? '#1a3a6a' : '#5a1a20';
      drawCircleIcon(ctx, p.champName, iconCx, iconCy, iconR);
      ctx.strokeStyle = color;
      ctx.lineWidth = isUser ? 2 : 1;
      ctx.beginPath(); ctx.arc(iconCx, iconCy, iconR, 0, Math.PI * 2); ctx.stroke();

      ctx.fillStyle = isUser ? COL.user : COL.text;
      ctx.font = (isUser ? '600 ' : '') + '10px system-ui,sans-serif';
      ctx.textAlign = 'left'; ctx.textBaseline = 'middle';
      ctx.fillText(p.champ, iconCx + iconR + 4, iconCy);
      ctx.textBaseline = 'alphabetic';
      ctx.globalAlpha = 1;
    }});
  }}

  // ── チームゴールドリード 推移 ─────────────────────────────────────────────
  function drawGoldDiff(canvas) {{
    if (!goldFrames || goldFrames.length < 2) return;
    const W = canvas.parentElement.clientWidth - 24;
    const H = 240;
    const ctx = setupCanvas(canvas, W, H);

    const PAD = {{ l: 68, r: 24, t: 28, b: 34 }};
    const cW = W - PAD.l - PAD.r;
    const cH = H - PAD.t - PAD.b;
    const maxAbs = Math.max(...goldFrames.map(f => Math.abs(f.diff)), 1000);
    const maxT   = goldFrames[goldFrames.length - 1].t;

    const tx = t => PAD.l + (t / maxT) * cW;
    const ty = d => PAD.t + cH / 2 - (d / maxAbs) * (cH * 0.46);
    const zeroY = ty(0);

    // 背景グリッド横線 (±25%, ±50%, 0)
    ctx.lineWidth = 0.5;
    [-0.5, -0.25, 0, 0.25, 0.5].forEach(ratio => {{
      ctx.strokeStyle = ratio === 0 ? 'rgba(255,255,255,0.12)' : COL.grid;
      const y = PAD.t + cH / 2 - ratio * cH * 0.46;
      ctx.beginPath(); ctx.moveTo(PAD.l, y); ctx.lineTo(PAD.l + cW, y); ctx.stroke();
    }});

    // 垂直グリッド (5分刻み)
    ctx.strokeStyle = COL.grid; ctx.lineWidth = 0.5;
    for (let m = 5; m * 60 < maxT; m += 5) {{
      const x = tx(m * 60);
      ctx.beginPath(); ctx.moveTo(x, PAD.t); ctx.lineTo(x, PAD.t + cH); ctx.stroke();
    }}

    // 塗り面積パス（ゼロラインで閉じる）
    const areaPath = new Path2D();
    areaPath.moveTo(tx(goldFrames[0].t), zeroY);
    goldFrames.forEach(f => areaPath.lineTo(tx(f.t), ty(f.diff)));
    areaPath.lineTo(tx(maxT), zeroY);
    areaPath.closePath();

    // 上半分クリップ（味方リード = 青）
    ctx.save();
    ctx.beginPath(); ctx.rect(PAD.l, PAD.t, cW, zeroY - PAD.t); ctx.clip();
    ctx.fillStyle = hexRgba(COL.friendB, 0.22);
    ctx.fill(areaPath);
    ctx.restore();

    // 下半分クリップ（敵リード = 赤）
    ctx.save();
    ctx.beginPath(); ctx.rect(PAD.l, zeroY, cW, PAD.t + cH - zeroY); ctx.clip();
    ctx.fillStyle = hexRgba(COL.enemyB, 0.22);
    ctx.fill(areaPath);
    ctx.restore();

    // ゴールドリードライン
    ctx.beginPath();
    goldFrames.forEach((f, i) =>
      i === 0 ? ctx.moveTo(tx(f.t), ty(f.diff)) : ctx.lineTo(tx(f.t), ty(f.diff))
    );
    ctx.strokeStyle = COL.friendB; ctx.lineWidth = 2; ctx.stroke();

    // X軸ラベル（5分刻み）
    ctx.fillStyle = COL.text; ctx.font = '10px system-ui,sans-serif'; ctx.textAlign = 'center';
    for (let m = 0; m * 60 <= maxT; m += 5)
      ctx.fillText(m + 'm', tx(m * 60), H - 10);

    // Y軸ラベル
    ctx.textAlign = 'right';
    [
      [maxAbs,  PAD.t + 10,         COL.friendB],
      [0,       zeroY + 4,          COL.text],
      [-maxAbs, PAD.t + cH - 2,     COL.enemyB],
    ].forEach(([v, y, col]) => {{
      ctx.fillStyle = col;
      ctx.fillText((v > 0 ? '+' : '') + fmtNum(v), PAD.l - 6, y);
    }});

    // 凡例ラベル
    ctx.textAlign = 'left'; ctx.font = '11px system-ui,sans-serif';
    ctx.fillStyle = COL.friendB; ctx.fillText(t('ally_lead'),  PAD.l + 6, PAD.t + 14);
    ctx.fillStyle = COL.enemyB;  ctx.fillText(t('enemy_lead'), PAD.l + 6, PAD.t + cH - 6);
  }}

  // ── 描画実行 ───────────────────────────────────────────────────────────────
  function renderAll() {{
    drawKDABreakdown(document.getElementById('chart-kda-breakdown'));
    drawLollipop(document.getElementById('chart-kda-ratio'),
      [...players].sort((a,b)=>b.kda-a.kda),   'kda',   v=>v.toFixed(2),
      [COL.friendA, COL.friendB], [COL.enemyA, COL.enemyB]);
    drawLollipop(document.getElementById('chart-dmg'),
      [...players].sort((a,b)=>b.dmg-a.dmg),   'dmg',   fmtNum,
      [COL.friendA, COL.friendB], [COL.enemyA, COL.enemyB]);
    drawLollipop(document.getElementById('chart-gold'),
      [...players].sort((a,b)=>b.gold-a.gold),  'gold',  fmtNum,
      [COL.friendA, COL.friendB], [COL.enemyA, COL.enemyB]);
    drawLollipop(document.getElementById('chart-cs'),
      [...players].sort((a,b)=>b.cs-a.cs),     'cs',    String,
      [COL.tealA, COL.tealB],   [COL.orangeA, COL.orangeB]);
    drawLollipop(document.getElementById('chart-vision'),
      [...players].sort((a,b)=>b.vision-a.vision), 'vision', String,
      [COL.tealA, COL.tealB],   [COL.orangeA, COL.orangeB]);
    drawLollipop(document.getElementById('chart-cc'),
      [...players].sort((a,b)=>b.cc-a.cc),     'cc',    v=>v+'s',
      [COL.tealA, COL.tealB],   [COL.orangeA, COL.orangeB]);
    drawScatter(document.getElementById('chart-scatter'));
    const friendPs = players.filter(p => p.teamId === friendTeamId);
    const enemyPs  = players.filter(p => p.teamId !== friendTeamId);
    drawRadar(document.getElementById('chart-radar-friend'), friendPs, players);
    drawRadar(document.getElementById('chart-radar-enemy'),  enemyPs,  players);
    drawLollipop(document.getElementById('chart-kp'),
      [...players].sort((a, b) => b.kp - a.kp),
      'kp', v => (v * 100).toFixed(0) + '%',
      [COL.friendA, COL.friendB], [COL.enemyA, COL.enemyB]);
    drawLollipop(document.getElementById('chart-dead'),
      [...players].sort((a, b) => b.dead_s - a.dead_s),
      'dead_s', v => ((v / gameDuration) * 100).toFixed(0) + '%',
      [COL.enemyA, COL.enemyB], [COL.friendA, COL.friendB]);
    drawGoldDiff(document.getElementById('chart-gold-diff'));
  }}

  window._renderAll = renderAll;
  requestAnimationFrame(renderAll);

  let _rt;
  window.addEventListener('resize', () => {{
    clearTimeout(_rt);
    _rt = setTimeout(renderAll, 150);
  }});
}})();
</script>
</body>
</html>
"""

    OUTPUT_DIR.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    out_html   = OUTPUT_DIR / f"out_{ts}.html"
    out_team   = OUTPUT_DIR / f"out_{ts}_team.csv"
    out_events = OUTPUT_DIR / f"out_{ts}_events.csv"

    out_html.write_text(html_doc, encoding="utf-8")

    if not args.no_csv:
        with out_team.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["teamId", "team", "pos", "player", "champ", "kills", "deaths", "assists", "kda", "cs", "gold", "dmg", "vision", "cc", "is_user"])
            for r in team100 + team200:
                w.writerow([r["teamId"], r["team"], r["pos"], r["player"], r["champ"], r["k"], r["d"], r["a"], f"{r['kda']:.4f}", r["cs"], r["gold"], r["dmg"], r["vision"], r["cc"], int(r["is_user"])])

        with out_events.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["t_ms", "time", "teamId", "team", "type", "text", "raw_json"])
            for e in events:
                w.writerow([e["t"], e["time"], e["teamId"], e["team"], e["type"], e["text"], json.dumps(e["raw"], ensure_ascii=False)])

    print("wrote:")
    print(" ", out_html)
    if not args.no_csv:
        print(" ", out_team)
        print(" ", out_events)
    print("used:")
    print(" ", match_path)
    print(" ", timeline_path)
    print(" ", champ_path)


if __name__ == "__main__":
    main()
    organize_all_outputs()
