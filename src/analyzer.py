"""AI-powered match analysis — supports Gemini (free) and Claude.

Reads the latest team-stats CSV and events CSV produced by lol_html_viewer_auto.py,
pre-processes the data into structured context, and calls an AI API for
specific, data-driven coaching feedback.

Usage:
    python src/analyzer.py                          # Gemini (free, default)
    python src/analyzer.py --provider claude        # Claude (paid)
    python src/analyzer.py --team out_team.csv --events out_events.csv
    python src/analyzer.py --lang en
"""

import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path

# Ensure emoji and Japanese text print correctly on Windows (cp932 consoles).
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent))
from constants import load_env  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "output"

_TEAM_GLOB = "out_*_team.csv"
_EVENTS_GLOB = "out_*_events.csv"

# Model identifiers per provider
_MODELS = {
    "gemini": "gemini-2.0-flash-lite",
    "claude": "claude-sonnet-4-6",
}

# Objective event types to include in the context window around deaths
_OBJECTIVE_TYPES = {"ELITE_MONSTER_KILL", "BUILDING_KILL"}


# ── CSV loaders ───────────────────────────────────────────────────────────────


def _load_team_csv(path: Path) -> list[dict]:
    """Load team stats CSV and return rows as a list of dicts with typed values."""
    rows = []
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append(
                {
                    "teamId": int(row["teamId"]),
                    "team": row["team"],
                    "pos": row["pos"],
                    "player": row["player"],
                    "champ": row["champ"],
                    "kills": int(row["kills"]),
                    "deaths": int(row["deaths"]),
                    "assists": int(row["assists"]),
                    "kda": float(row["kda"]),
                    "cs": int(row["cs"]),
                    "gold": int(row["gold"]),
                    "dmg": int(row["dmg"]),
                    "vision": int(row["vision"]),
                    "cc": int(row["cc"]),
                    "kp": float(row.get("kp", 0)),
                    "dead_s": int(row.get("dead_s", 0)),
                    "is_user": int(row["is_user"]) == 1,
                }
            )
    return rows


def _load_events_csv(path: Path) -> list[dict]:
    """Load events CSV and return rows as a list of dicts with typed timestamps."""
    rows = []
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append(
                {
                    "t_ms": int(row["t_ms"]),
                    "time": row["time"],
                    "teamId": int(row["teamId"]) if row["teamId"] else None,
                    "team": row["team"],
                    "type": row["type"],
                    "text": row["text"],
                    "raw": json.loads(row["raw_json"]),
                }
            )
    return rows


# ── File discovery ─────────────────────────────────────────────────────────────


def _find_latest_csv_pair(base_dir: Path) -> tuple[Path, Path]:
    """Return (team_csv_path, events_csv_path) for the most recent output set.

    Raises:
        FileNotFoundError: if no matching CSVs are found in base_dir.
    """
    team_files = sorted(base_dir.glob(_TEAM_GLOB), key=lambda p: p.stat().st_mtime, reverse=True)
    if not team_files:
        raise FileNotFoundError(f"No team CSV found in {base_dir}")

    team_path = team_files[0]
    # Derive the corresponding events file by replacing the suffix
    events_path = Path(str(team_path).replace("_team.csv", "_events.csv"))
    if not events_path.exists():
        events_files = sorted(
            base_dir.glob(_EVENTS_GLOB), key=lambda p: p.stat().st_mtime, reverse=True
        )
        if not events_files:
            raise FileNotFoundError(f"No events CSV found in {base_dir}")
        events_path = events_files[0]

    return team_path, events_path


# ── Pre-processing ─────────────────────────────────────────────────────────────


def _rank_in_group(rows: list[dict], metric: str, user_val) -> str:
    """Return ordinal rank string (e.g. '1位/5人中') for user within rows."""
    vals = sorted([r[metric] for r in rows], reverse=True)
    rank = vals.index(user_val) + 1
    return f"{rank}位 / {len(rows)}人中"


def _build_team_summary(rows: list[dict]) -> dict:
    """Separate rows into ally/enemy lists and locate the user row.

    Returns:
        Dict with keys: user, ally, enemy, ally_team_id, enemy_team_id.
    """
    user = next((r for r in rows if r["is_user"]), None)
    if user is None:
        raise ValueError("No is_user=1 row found in team CSV")

    ally = [r for r in rows if r["teamId"] == user["teamId"]]
    enemy = [r for r in rows if r["teamId"] != user["teamId"]]
    enemy_team_id = enemy[0]["teamId"] if enemy else (200 if user["teamId"] == 100 else 100)

    return {
        "user": user,
        "ally": ally,
        "enemy": enemy,
        "ally_team_id": user["teamId"],
        "enemy_team_id": enemy_team_id,
    }


def _find_opponent(user: dict, enemy: list[dict]) -> dict | None:
    """Return the enemy player with the same position as the user, or None."""
    pos = user.get("pos", "")
    if not pos:
        return None
    return next((r for r in enemy if r["pos"] == pos), None)


def _death_sequences(user: dict, events: list[dict], window_ms: int = 60_000) -> list[dict]:
    """Find events where the user was killed and collect nearby objective events.

    Args:
        user:      User's team row dict (needs 'champ' key).
        events:    All events from the events CSV.
        window_ms: Time window in ms before/after a death to scan for objectives.

    Returns:
        List of dicts, one per user death, with nearby objective events attached.
    """
    user_champ = user["champ"]
    sequences = []

    for ev in events:
        raw = ev.get("raw", {})
        # Detect kills where the user was the victim
        if ev["type"] != "CHAMPION_KILL":
            continue
        # Match by champion name in the Japanese event text
        if user_champ not in ev["text"] or "をキル" not in ev["text"]:
            continue
        # Confirm victim by checking raw victimId exists
        if not raw.get("victimId"):
            continue

        t = ev["t_ms"]
        nearby = [
            e
            for e in events
            if e["type"] in _OBJECTIVE_TYPES and abs(e["t_ms"] - t) <= window_ms
        ]
        sequences.append(
            {
                "time": ev["time"],
                "death_text": ev["text"],
                "nearby_objectives": [
                    {"time": e["time"], "text": e["text"], "delta_s": (e["t_ms"] - t) // 1000}
                    for e in nearby
                ],
            }
        )

    return sequences


def _objective_totals(events: list[dict], ally_team_id: int) -> dict:
    """Count objectives (dragon, baron, herald, tower) per side.

    Returns:
        Dict with keys: dragon, baron, herald, tower — each a dict with ally/enemy counts.
    """
    totals: dict[str, dict[str, int]] = {
        "dragon": {"ally": 0, "enemy": 0},
        "baron": {"ally": 0, "enemy": 0},
        "herald": {"ally": 0, "enemy": 0},
        "tower": {"ally": 0, "enemy": 0},
    }
    for ev in events:
        raw = ev.get("raw", {})
        side = "ally" if ev["teamId"] == ally_team_id else "enemy"
        if ev["type"] == "ELITE_MONSTER_KILL":
            m = raw.get("monsterType", "")
            if m == "DRAGON":
                totals["dragon"][side] += 1
            elif m == "BARON_NASHOR":
                totals["baron"][side] += 1
            elif m == "RIFTHERALD":
                totals["herald"][side] += 1
        elif ev["type"] == "BUILDING_KILL":
            if raw.get("buildingType") == "TOWER_BUILDING":
                totals["tower"][side] += 1
    return totals


# ── Prompt builder ─────────────────────────────────────────────────────────────


def _build_system_prompt(lang: str) -> str:
    """Return the system prompt for the coaching AI in the given language."""
    if lang == "ja":
        return (
            "あなたはリーグ・オブ・レジェンド（LoL）の専門コーチです。"
            "スウィフトプレイの試合データを元に、プレイヤーの強みと改善点を"
            "具体的かつ建設的に分析してください。"
            "数値の羅列ではなく、「なぜその数値になったか」「どうすれば改善できるか」を"
            "タイムラインの根拠と共に説明してください。"
            "回答はMarkdown形式で出力してください。"
        )
    return (
        "You are a specialist League of Legends coach. "
        "Analyze the provided Swift Play match data and give the player "
        "specific, constructive feedback on their strengths and areas to improve. "
        "Focus on the 'why' behind the numbers and back your points with timeline evidence. "
        "Format your response in Markdown."
    )


def _build_prompt(
    team_rows: list[dict],
    events: list[dict],
    game_result: str,
    lang: str,
) -> str:
    """Build the structured analysis prompt from pre-processed match data.

    Args:
        team_rows:   All 10 player rows from the team CSV.
        events:      All events from the events CSV.
        game_result: ``"勝利"`` or ``"敗北"`` (or ``"Win"``/``"Loss"`` for en).
        lang:        ``"ja"`` or ``"en"``.

    Returns:
        A complete prompt string ready to pass to the AI API.
    """
    summary = _build_team_summary(team_rows)
    user = summary["user"]
    ally = summary["ally"]
    enemy = summary["enemy"]
    opponent = _find_opponent(user, enemy)
    deaths = _death_sequences(user, events)
    objectives = _objective_totals(events, summary["ally_team_id"])

    # Infer game duration from last event timestamp
    game_duration_s = max((e["t_ms"] for e in events), default=1) // 1000 or 1
    dead_pct = user["dead_s"] / game_duration_s * 100

    lines: list[str] = []

    # ── Match overview ──────────────────────────────────────────────────────
    lines += [
        "## 試合概要" if lang == "ja" else "## Match Overview",
        f"- 勝敗: {game_result}" if lang == "ja" else f"- Result: {game_result}",
        f"- チャンピオン: {user['champ']}（{user['pos']}）"
        if lang == "ja"
        else f"- Champion: {user['champ']} ({user['pos']})",
        f"- スコア: {user['kills']}/{user['deaths']}/{user['assists']}（KDA {user['kda']:.2f}）"
        if lang == "ja"
        else f"- Score: {user['kills']}/{user['deaths']}/{user['assists']} (KDA {user['kda']:.2f})",
        f"- KP: {user['kp'] * 100:.1f}%　デス時間占有率: {dead_pct:.1f}%"
        if lang == "ja"
        else f"- Kill Participation: {user['kp'] * 100:.1f}%  Dead Time: {dead_pct:.1f}%",
        "",
    ]

    # ── Ally team ranking ──────────────────────────────────────────────────
    lines.append("## 本人スタッツ（味方内順位）" if lang == "ja" else "## User Stats (Rank Among Allies)")
    header = "| 指標 | 本人 | チーム平均 | 味方内順位 |" if lang == "ja" else "| Metric | User | Team Avg | Rank |"
    lines.append(header)
    lines.append("|---|---|---|---|")

    metrics = [
        ("dmg", "ダメージ" if lang == "ja" else "Damage"),
        ("gold", "ゴールド" if lang == "ja" else "Gold"),
        ("cs", "CS"),
        ("kda", "KDA"),
        ("vision", "視界スコア" if lang == "ja" else "Vision Score"),
        ("cc", "CC時間" if lang == "ja" else "CC Time"),
    ]
    for key, label in metrics:
        val = user[key]
        avg = sum(r[key] for r in ally) / len(ally)
        rank = _rank_in_group(ally, key, val)
        lines.append(f"| {label} | {val} | {avg:.1f} | {rank} |")
    lines.append("")

    # ── Lane opponent comparison ──────────────────────────────────────────
    if opponent:
        lines.append(
            f"## 対面比較（{user['pos']}：{user['champ']} vs {opponent['champ']}）"
            if lang == "ja"
            else f"## Lane Matchup ({user['pos']}: {user['champ']} vs {opponent['champ']})"
        )
        lines.append("| 指標 | 本人 | 対面 | 差 |" if lang == "ja" else "| Metric | User | Opponent | Diff |")
        lines.append("|---|---|---|---|")
        for key, label in metrics:
            u_val = user[key]
            o_val = opponent[key]
            diff = u_val - o_val if isinstance(u_val, (int, float)) else "-"
            sign = "+" if isinstance(diff, float) and diff >= 0 else ""
            lines.append(f"| {label} | {u_val} | {o_val} | {sign}{diff:.2f} |")
        lines.append("")

    # ── Death sequences ──────────────────────────────────────────────────
    if deaths:
        lines.append(
            f"## 死亡シーケンス（{len(deaths)}回）前後60秒のオブジェクト"
            if lang == "ja"
            else f"## Death Sequences ({len(deaths)} deaths) — Nearby Objectives (±60s)"
        )
        for d in deaths:
            nearby = d["nearby_objectives"]
            if nearby:
                obj_lines = "; ".join(
                    f"{o['time']} {o['text']} ({'+' if o['delta_s'] >= 0 else ''}{o['delta_s']}秒)"
                    for o in nearby
                )
            else:
                obj_lines = "なし（孤立死の可能性）" if lang == "ja" else "none (possibly isolated death)"
            lines.append(f"- {d['time']} {d['death_text']}")
            lines.append(f"  → 周辺OBJ: {obj_lines}")
        lines.append("")

    # ── Objective totals ─────────────────────────────────────────────────
    lines.append("## オブジェクト集計" if lang == "ja" else "## Objective Summary")
    obj_labels = [
        ("dragon", "ドラゴン" if lang == "ja" else "Dragon"),
        ("baron", "バロン" if lang == "ja" else "Baron"),
        ("herald", "リフトヘラルド" if lang == "ja" else "Rift Herald"),
        ("tower", "タワー" if lang == "ja" else "Tower"),
    ]
    for key, label in obj_labels:
        a = objectives[key]["ally"]
        e = objectives[key]["enemy"]
        lines.append(f"- {label}: 味方 {a} / 敵 {e}" if lang == "ja" else f"- {label}: Ally {a} / Enemy {e}")
    lines.append("")

    # ── Analysis request ─────────────────────────────────────────────────
    if lang == "ja":
        lines += [
            "## 分析依頼",
            "以下の3点を答えてください。数値の羅列ではなく、タイムラインや対面比較など具体的な根拠を示してください。",
            "",
            "1. **勝敗要因** — この試合の勝敗を決定づけた主な要因を、本人のプレーとチーム全体の両面から説明してください。",
            "2. **改善ポイント** — 本人が改善できた具体的な場面を指摘してください（タイムラインの死亡シーケンスを参照）。",
            "3. **次の試合での優先事項** — 次の試合で意識すべき最優先事項を2〜3点、具体的なアクションとして教えてください。",
        ]
    else:
        lines += [
            "## Analysis Request",
            "Answer the following 3 points. Use concrete evidence from the timeline and lane matchup — avoid generic commentary.",
            "",
            "1. **Win/Loss Factors** — What were the main factors that determined the outcome? Cover both the user's play and the team as a whole.",
            "2. **Improvement Points** — Identify specific moments where the user could have played differently (reference the death sequences).",
            "3. **Top Priorities for Next Game** — Give 2–3 concrete, actionable things to focus on next game.",
        ]

    return "\n".join(lines)


# ── API calls ─────────────────────────────────────────────────────────────────


def _call_gemini(prompt: str, api_key: str, lang: str) -> str:
    """Send the analysis prompt to Gemini and return the response text.

    Args:
        prompt:  The user-facing analysis prompt.
        api_key: Google AI Studio API key (GEMINI_API_KEY in .env).
        lang:    ``"ja"`` or ``"en"`` — used in the system instruction.

    Returns:
        The model's response as a string.
    """
    from google import genai  # lazy import — only needed for this provider
    from google.genai import types

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=_MODELS["gemini"],
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=_build_system_prompt(lang),
        ),
    )
    return response.text


def _call_claude(prompt: str, api_key: str, lang: str) -> str:
    """Send the analysis prompt to Claude and return the response text.

    Args:
        prompt:  The user-facing analysis prompt.
        api_key: Anthropic API key (ANTHROPIC_API_KEY in .env).
        lang:    ``"ja"`` or ``"en"`` — used in the system prompt.

    Returns:
        The model's response as a string.
    """
    import anthropic  # lazy import — only needed for this provider

    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model=_MODELS["claude"],
        max_tokens=2048,
        system=_build_system_prompt(lang),
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


# ── Entry point ───────────────────────────────────────────────────────────────


def main() -> None:
    """CLI entry point: load CSVs, build prompt, call AI, save report."""
    ap = argparse.ArgumentParser(description="AI-powered LoL match analysis")
    ap.add_argument("--team", default=None, help="Path to team stats CSV (default: latest in output/)")
    ap.add_argument("--events", default=None, help="Path to events CSV (default: latest in output/)")
    ap.add_argument(
        "--result",
        default=None,
        help="Match result: 'win' / 'loss' (or '勝利' / '敗北'). Inferred by AI if omitted.",
    )
    ap.add_argument("--lang", default="ja", choices=["ja", "en"], help="Report language (default: ja)")
    ap.add_argument(
        "--provider",
        default="gemini",
        choices=["gemini", "claude"],
        help="AI provider: gemini (free, default) or claude (paid)",
    )
    args = ap.parse_args()

    env = load_env(ROOT / ".env")

    # Resolve API key for the chosen provider
    if args.provider == "gemini":
        api_key = env.get("GEMINI_API_KEY", "")
        key_name = "GEMINI_API_KEY"
        caller = _call_gemini
    else:
        api_key = env.get("ANTHROPIC_API_KEY", "")
        key_name = "ANTHROPIC_API_KEY"
        caller = _call_claude

    if not api_key:
        print(
            f"❌ {key_name} が .env に見つかりません — {key_name}=... を追記してください"
            if args.lang == "ja"
            else f"❌ {key_name} not found in .env — add {key_name}=... and retry"
        )
        sys.exit(1)

    # Resolve CSV paths
    if args.team and args.events:
        team_path = Path(args.team).expanduser().resolve()
        events_path = Path(args.events).expanduser().resolve()
    else:
        team_path, events_path = _find_latest_csv_pair(OUTPUT_DIR)

    print(
        f"📂 読み込み中: {team_path.name} / {events_path.name}"
        if args.lang == "ja"
        else f"📂 Loading: {team_path.name} / {events_path.name}"
    )

    team_rows = _load_team_csv(team_path)
    events = _load_events_csv(events_path)

    # Infer or accept match result
    if args.result:
        game_result = args.result
    else:
        game_result = "不明（データから推定してください）" if args.lang == "ja" else "Unknown (infer from data)"

    prompt = _build_prompt(team_rows, events, game_result, args.lang)

    provider_label = "Gemini" if args.provider == "gemini" else "Claude"
    print(
        f"🤖 {provider_label} に送信中..."
        if args.lang == "ja"
        else f"🤖 Sending to {provider_label}..."
    )

    report = caller(prompt, api_key, args.lang)

    # Save report
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    out_path = OUTPUT_DIR / f"analysis_{ts}.md"
    OUTPUT_DIR.mkdir(exist_ok=True)
    out_path.write_text(report, encoding="utf-8")

    print(
        f"✅ レポートを保存しました: {out_path}"
        if args.lang == "ja"
        else f"✅ Report saved: {out_path}"
    )
    print()
    print(report)


if __name__ == "__main__":
    main()
