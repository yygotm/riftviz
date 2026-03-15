"""Project-wide constants and shared utilities."""


# ── .env parser ──────────────────────────────────────────────────────────────

def load_env(path):
    """Parse a .env file and return a dict of key/value pairs."""
    env = {}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                env[key.strip()] = val.strip()
    except FileNotFoundError:
        pass
    return env


# ── Platform / region mapping ─────────────────────────────────────────────────

PLATFORM_TO_REGION: dict[str, str] = {
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

# ── Queue presets ─────────────────────────────────────────────────────────────

QUEUE_PRESETS: dict[str, int] = {
    "swift": 1700,
    "ranked-solo": 420,
    "ranked-flex": 440,
    "normal-draft": 400,
    "normal-blind": 430,
    "aram": 450,
}

# ── Timeline event filter ─────────────────────────────────────────────────────

ALLOWED_EVENT_TYPES: set[str] = {
    "CHAMPION_KILL",
    "ELITE_MONSTER_KILL",
    "BUILDING_KILL",
}

# ── Bilingual name maps ───────────────────────────────────────────────────────

MONSTER_NAMES: dict[str, dict[str, str]] = {
    "DRAGON":       {"ja": "ドラゴン",       "en": "Dragon"},
    "BARON_NASHOR": {"ja": "バロン",         "en": "Baron Nashor"},
    "RIFTHERALD":   {"ja": "リフトヘラルド", "en": "Rift Herald"},
}

LANE_NAMES: dict[str, dict[str, str]] = {
    "TOP_LANE": {"ja": "トップ", "en": "Top"},
    "MID_LANE": {"ja": "ミッド", "en": "Mid"},
    "BOT_LANE": {"ja": "ボット", "en": "Bot"},
}
