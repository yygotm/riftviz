# riftviz

A local League of Legends match analysis tool that fetches data from the Riot Games API, generates a self-contained HTML viewer with interactive charts, and produces AI-powered coaching reports.

---

## Demo

<img width="1280" alt="Stats tables" src="https://github.com/user-attachments/assets/1addc6b7-9edd-4d24-8f8d-1c7d9808873b" />
<img width="1280" alt="KDA Breakdown" src="https://github.com/user-attachments/assets/2f62e7a6-fb82-434a-b0a9-9e5e129534ee" />
<img width="1280" alt="KDA Ratio / Damage / Gold" src="https://github.com/user-attachments/assets/47bae183-6205-4e90-b4b5-a53cd1b252da" />
<img width="1280" alt="CS / Vision / CC / Scatter plot" src="https://github.com/user-attachments/assets/cd22b139-afd4-4cf5-98ad-39c855ce9ec9" />
<img width="1280" alt="Performance radar (Ally / Enemy)" src="https://github.com/user-attachments/assets/c949b35f-13b9-4807-a2c0-3ab76f3f93e8" />
<img width="1280" alt="Kill Participation / Dead Time" src="https://github.com/user-attachments/assets/4c2ca6d9-8803-4ad4-818d-6f45efb6996d" />
<img width="1280" alt="Team gold lead timeline" src="https://github.com/user-attachments/assets/9576d5d0-31ec-420a-ac97-416185c4972a" />
<img width="1280" alt="Event timeline" src="https://github.com/user-attachments/assets/64a40b29-e602-4c9e-9dd8-90a16d1a7677" />

---

## Features

**Stats Charts (Canvas)**
- KDA breakdown — proportional bars for Deaths / Kills / Assists
- Lollipop charts — KDA ratio, Damage, Gold, CS, Vision, CC
- Damage dealt vs. received scatter plot
- Team performance radar chart
- Kill Participation % and Dead Time % lollipops
- Team gold lead timeline

**Event Timeline**
- Champion icon-based kill / tower / monster events
- Assist icons stacked vertically next to the killer
- Color-coded friend (blue) / enemy (red) rows
- Gold border highlight for the tracked player's events
- JA / EN language toggle button

**AI Analysis (`analyzer.py`)**
- Death × objective correlation — finds nearby dragon/baron/tower events within ±60 s of each death
- Lane matchup comparison against the lane opponent
- Team-rank for damage, gold, CS, KDA, vision, CC
- Saves a Markdown coaching report to `output/analysis_*.md`
- Supports **Gemini** (free tier, default) and **Claude** (paid)

---

## Requirements

- Python 3.10+
- Riot Games API key — get one at [developer.riotgames.com](https://developer.riotgames.com)
- *(Optional)* Gemini API key for AI analysis — get one free at [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)

---

## Setup

```bash
git clone https://github.com/yygotm/riftviz.git
cd riftviz
pip install requests google-genai anthropic   # anthropic only needed for --provider claude
```

### 1. Get a Riot API Key

1. Go to [developer.riotgames.com](https://developer.riotgames.com) and log in with your Riot account
2. On the dashboard, click **"GENERATE API KEY"**
3. Copy the key (format: `RGAPI-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`)

> **Note:** Development API keys expire every 24 hours. Return to the dashboard and regenerate before each session.

### 2. Get your PUUID

Your Riot ID looks like `PlayerName#TAG`. Open this URL in your browser — use the routing region that matches your platform (e.g. `asia` for JP1/KR, `americas` for NA1, `europe` for EUW1):

```
https://{routing}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{gameName}/{tagLine}?api_key=RGAPI-xxxx
```

Example — JP1/KR players use `asia`:
```
https://asia.api.riotgames.com/riot/account/v1/accounts/by-riot-id/PlayerName/TAG?api_key=RGAPI-xxxx
```

The response looks like:
```json
{
  "puuid": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  "gameName": "PlayerName",
  "tagLine": "TAG"
}
```

### 3. Create `.env`

Create a `.env` file in the project root:

```
API_KEY=RGAPI-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
PLATFORM=JP1
PUUID=your-puuid-here
LANG=ja

# Optional — required only for Step 3 (AI analysis)
GEMINI_API_KEY=AIzaSy...          # free tier: aistudio.google.com/app/apikey
ANTHROPIC_API_KEY=sk-ant-...      # paid: console.anthropic.com
```

**PLATFORM** options: `JP1` `KR` `NA1` `EUW1` `EUN1` `BR1` `LA1` `LA2` `TR1` `RU` `OC1` `PH2` `SG2` `TH2` `TW2` `VN2`

**LANG** options: `ja` (default) or `en`

---

## Usage

### Step 1 — Fetch the latest match and generate HTML

```bash
# Swift Play (default)
python src/fetch_match_data.py

# Ranked Solo/Duo
python src/fetch_match_data.py --queue ranked-solo
```

Pulls the latest match from the Riot API, saves JSON to `data/`, and automatically generates the HTML viewer + CSV.

**`--queue` / `-q` options:**

| Name | Queue ID | Mode |
|---|---|---|
| `swift` | 1700 | Swift Play (default) |
| `ranked-solo` | 420 | Ranked Solo/Duo |
| `ranked-flex` | 440 | Ranked Flex |
| `normal-draft` | 400 | Normal Draft |
| `normal-blind` | 430 | Normal Blind |
| `aram` | 450 | ARAM |

You can also pass a numeric queue ID directly: `--queue 900`

### Step 2 — Regenerate HTML from saved data

```bash
python src/lol_html_viewer_auto.py
# or on Windows:
build_viewer.bat
```

**Options:**

```bash
# Skip CSV output
python src/lol_html_viewer_auto.py --no-csv

# Use a specific data directory
python src/lol_html_viewer_auto.py --dir path/to/dir

# Regenerate HTML for all archived matches
python src/lol_html_viewer_auto.py --dir data/archive --all

# Regenerate the 10 most recent archived matches
python src/lol_html_viewer_auto.py --dir data/archive --all -n 10
```

Output is saved to `output/out_TIMESTAMP.html` (single match) or `output/out_JP1_MATCHID.html` (batch). Open directly in your browser — no server needed.

### Step 3 — AI analysis (requires `GEMINI_API_KEY` or `ANTHROPIC_API_KEY` in `.env`)

```bash
# Analyze the latest match with Gemini (free, default)
python src/analyzer.py

# Use Claude instead
python src/analyzer.py --provider claude
```

Reads the latest CSV pair from `output/`, builds a structured prompt (team ranking, lane matchup, death sequences, objective totals), calls the AI, and saves `output/analysis_TIMESTAMP.md`.

**Options:**

| Flag | Default | Description |
|---|---|---|
| `--provider` | `gemini` | AI provider: `gemini` (free) or `claude` (paid) |
| `--lang` | `ja` | Report language: `ja` or `en` |
| `--team` | *(latest)* | Path to a specific team stats CSV |
| `--events` | *(latest)* | Path to a specific events CSV |

---

## Project Structure

```
riftviz/
├── .env                         # API_KEY, PLATFORM, PUUID, LANG, GEMINI_API_KEY (gitignored)
├── build_viewer.bat             # Windows shortcut for Step 2
├── src/
│   ├── fetch_match_data.py      # Step 1 — fetch match data from Riot API
│   ├── lol_html_viewer_auto.py  # Step 2 — generate the HTML viewer + CSV
│   ├── analyzer.py              # Step 3 — AI coaching report via Gemini / Claude
│   ├── constants.py             # Shared constants (platform map, queue presets, etc.)
│   └── templates/               # Inlined CSS / JS for the self-contained HTML
├── assets/
│   └── 00_champ.json            # Champion ID → name fallback map
├── data/                        # Match JSON files (gitignored)
│   └── archive/                 # Previous match JSONs (auto-archived)
└── output/                      # Generated HTML, CSV, and analysis reports (gitignored)
    └── archive/                 # Previous outputs (auto-archived after each run)
```

---

## Disclaimer

> riftviz isn't endorsed by Riot Games and doesn't reflect the views or opinions of Riot Games or anyone officially involved in producing or managing Riot Games properties. League of Legends and Riot Games are trademarks or registered trademarks of Riot Games, Inc.

Champion icons are loaded at runtime from the [Data Dragon CDN](https://developer.riotgames.com/docs/lol#data-dragon). No image assets are stored in this repository.

---

## License

MIT — applies to the original source code in this repository.
Riot Games assets and API data are subject to the [Riot Games Terms of Service](https://www.riotgames.com/en/terms-of-service).
