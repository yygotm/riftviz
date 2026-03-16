# riftviz

A local League of Legends match analysis tool that fetches data from the Riot Games API, generates a self-contained HTML viewer with interactive charts, and produces AI-powered coaching reports.

---

## Demo

<img width="1400" height="697" alt="Stats tables" src="https://github.com/user-attachments/assets/93eaa2ae-cbc7-4d0f-9cd8-0647b9c5058d" />
<img width="1384" height="627" alt="KDA Breakdown" src="https://github.com/user-attachments/assets/0195351d-367c-4610-963f-b88510bdddf7" />
<img width="924" height="607" alt="KDA Ratio / Damage" src="https://github.com/user-attachments/assets/8667ff8a-1a6d-4017-8b84-6e32e99519ef" />
<img width="1384" height="1210" alt="Gold / CS / Vision / CC" src="https://github.com/user-attachments/assets/e1816570-4b83-4abd-ae93-3a2f315ef89b" />
<img width="1384" height="411" alt="Damage dealt vs received scatter plot" src="https://github.com/user-attachments/assets/e31fbcff-cf02-48cb-9e60-687b638e230a" />
<img width="1384" height="1034" alt="Performance radar (Ally / Enemy) + KP / Dead Time" src="https://github.com/user-attachments/assets/5d11873c-530e-47dc-8140-1b4aa695fce4" />
<img width="1384" height="311" alt="Team gold lead timeline" src="https://github.com/user-attachments/assets/18b940de-0b1b-4047-abb9-244d9c53d5d4" />
<img width="1358" height="900" alt="Event timeline" src="https://github.com/user-attachments/assets/8d26b4a0-e4d7-402c-ae70-cff9ff32575a" />

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
- Saves an HTML report to `output/analysis_*.html` — open directly in your browser
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
pip install -r requirements.txt
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

Copy the example and fill in your keys:

```bash
# Mac / Git Bash / PowerShell
cp .env.example .env

# Windows (Command Prompt / cmd.exe)
copy .env.example .env
```

Or create it manually:

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

# Debug: print raw API URL and response
python src/fetch_match_data.py --debug

# Windows shortcut (double-click or run from terminal)
riftviz.bat
riftviz.bat --queue ranked-solo
```

Pulls the latest match from the Riot API, saves JSON to `data/`, and automatically generates the HTML viewer + CSV.

**Options:**

| Flag | Description |
|---|---|
| `--queue` / `-q` | Queue to fetch (default: `swift`). See table below. |
| `--debug` | Print raw API URL and response — useful when no matches are returned. |

**`--queue` presets:**

| Name | Queue ID | Mode |
|---|---|---|
| `swift` | 480 | Swift Play (default) |
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

Reads the latest CSV pair from `output/`, builds a structured prompt (team ranking, lane matchup, death sequences, objective totals), calls the AI, and saves `output/analysis_TIMESTAMP.html`. Open the file directly in your browser — no server needed.

**Options:**

| Flag | Default | Description |
|---|---|---|
| `--provider` | `gemini` | AI provider: `gemini` (free) or `claude` (paid) |
| `--lang` | *(from `.env` `LANG`, default `ja`)* | Report language: `ja` or `en` |
| `--team` | *(latest)* | Path to a specific team stats CSV |
| `--events` | *(latest)* | Path to a specific events CSV |

<details>
<summary>📊 Example analysis output (Gemini · English · Win)</summary>

> Generated by `python src/analyzer.py --lang en`
> Champion: **Jinx (BOTTOM)** · 7/9/15 · Win

---

## Match Analysis: Jinx (BOTTOM) - Win (7/9/15)

### 1. Win/Loss Factors

Your team's victory was a testament to your ability to scale and deliver high damage, despite a very rough start.

**Factors Contributing to the Win:**

- **Exceptional Damage Output (User):** Despite your high death count, you were the top damage dealer on your team (38209, 1st). This clearly demonstrates that when you were alive and in a position to fight, you capitalized on Jinx's hyper-carry potential. This high damage output in the mid-to-late game was a critical factor in your team's ability to win teamfights and secure objectives, especially evident in how your team secured Baron at 21:40 which often leads to the game-ending push.
- **Strong Resource Generation (User):** Being 1st in Gold (20541) and CS (139) among your teammates highlights your efficiency in acquiring resources. This allowed you to reach your item power spikes and ultimately output that significant damage, validating Jinx's scaling nature.
- **Better KDA than Opponent (User vs. Opponent Jinx):** While your KDA was low for your team, your 2.44 KDA was notably better than the enemy Jinx's 1.91. This suggests that despite the enemy Jinx having higher raw damage, gold, and CS, your contributions (kills and assists relative to deaths) were more impactful towards your team's success in crucial moments.
- **Team Objective Control:** Your team secured Baron (1-0) and had a dragon lead (2-1), which are massive win conditions. The Baron take at 21:40 (followed by enemy inhibitor/tower takes) was likely the decisive push that sealed the victory.

**Factors that Made the Game Difficult / Could Have Led to a Loss:**

- **Excessive Early Game Deaths (User):** Your 9 deaths were the primary negative factor. Crucially, **7 of these 9 deaths occurred before 7:30 minutes into the game.** This is an extremely damaging start for an immobile hyper-carry like Jinx, feeding significant gold to the enemy team and severely delaying your power spikes.
  - **Timeline Evidence:** You died at 00:45, 00:47, 02:32, 04:56, 04:59, 06:28, and 07:08. This meant you were effectively 0/7/0 at a point when Jinx should be focused on safely farming and scaling.
- **Lane Disadvantage:** Despite being 1st in damage, gold, and CS on your team, you were still behind the **enemy Jinx** in all these categories. The enemy Jinx dealt 7048 more damage, had 1516 more gold, and 16 more CS. This indicates that the enemy Jinx was getting more resources and impact from the lane matchup directly, which made your team's win harder to achieve.

### 2. Improvement Points

Your primary area for improvement revolves around early game decision-making and survival.

- **Avoid Over-Aggression/Being Caught Out in the Early Game:**
  - **Specific Moments:** Your deaths at **00:45 (killed by enemy Jinx) and 00:47 (killed by enemy Sett)** are critical. Dying twice before the first minute mark is incredibly punishing and puts you at a severe disadvantage for the entire laning phase.
  - **Improvement:** Focus on a safe and passive level 1-3. Do not contest neutral territory without explicit knowledge of your support and jungler's positioning. Prioritize getting to lane, securing your first few minions, and avoiding unnecessary trades.
- **Respect Enemy Jungle & Support Pressure:**
  - **Specific Moments:** You died to Jarvan IV three times (**02:32, 04:59, 07:08**) and Blitzcrank twice (**04:56, 06:28**) within the first 7 minutes. These chained deaths highlight a pattern of being vulnerable to ganks and pick attempts.
  - **Improvement:** Enhance your mini-map awareness and jungle tracking. Place defensive wards in river brushes and tri-bushes. When facing a Blitzcrank, actively position behind your minions to block his Rocket Grab. Save **Chompers (E)** as a defensive tool to deter engages or create space.
- **Re-evaluate and Adapt After Deaths:**
  - **Specific Moments:** The consecutive deaths (e.g., 00:45/00:47 and 04:56/04:59) indicate you may not have adapted your playstyle immediately after being killed.
  - **Improvement:** After each death, consider "Why did I die?" Adjust your approach immediately — be more cautious, farm under tower, or wait for your team to group.

### 3. Top Priorities for Next Game

1. **Prioritize Surviving the Laning Phase (0–10 Minutes):**
   Aim for **zero deaths in the first 10 minutes**. Jinx scales incredibly well; simply surviving and farming is a win condition for her.

2. **Enhance Vision Control & Map Awareness for Safety:**
   Purchase a **Control Ward** on your first back and place it defensively in the river bush or tri-bush. Constantly glance at your mini-map and track the enemy jungler's last known location.

3. **Refine Positioning and Kiting in Skirmishes/Teamfights:**
   Focus on maintaining **maximum attack range** with your rockets (Q) and kiting back. Use **Chompers (E)** strategically to zone or disengage from persistent threats rather than as an offensive tool.

By focusing on these areas, you can leverage your strong scaling and damage output more consistently, turning early game deficits into reliable late-game carries.

</details>

---

## Project Structure

```
riftviz/
├── .env                         # API_KEY, PLATFORM, PUUID, LANG, GEMINI_API_KEY (gitignored)
├── .env.example                 # Template — copy to .env and fill in your keys
├── riftviz.bat                  # Windows shortcut for Step 1 (fetch + generate HTML)
├── build_viewer.bat             # Windows shortcut for Step 2 (regenerate HTML only)
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
