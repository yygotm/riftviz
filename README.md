# riftviz

A local League of Legends match analysis tool that fetches data from the Riot Games API and generates a self-contained HTML viewer with interactive charts and a visual event timeline.

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

---

## Requirements

- Python 3.10+
- Riot Games API key — get one at [developer.riotgames.com](https://developer.riotgames.com)

---

## Setup

```bash
git clone https://github.com/yygotm/riftviz.git
cd riftviz
```

### 1. Get a Riot API Key

1. Go to [developer.riotgames.com](https://developer.riotgames.com) and log in with your Riot account
2. On the dashboard, click **"GENERATE API KEY"**
3. Copy the key (format: `RGAPI-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`)

> **Note:** Development API keys expire every 24 hours. Return to the dashboard and regenerate before each session.

Create a `.env` file in the project root with the following three values:

```
API_KEY=RGAPI-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
PLATFORM=JP1
PUUID=your-puuid-here
```

**PLATFORM** options: `JP1` `KR` `NA1` `EUW1` `EUN1` `BR1` `LA1` `LA2` `TR1` `RU` `OC1` `PH2` `SG2` `TH2` `TW2` `VN2`

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

Copy the `puuid` value into your `.env` file as `PUUID=...`.

---

## Usage

### Step 1 — Fetch the latest match and generate HTML

```bash
python src/match.py
```

Pulls the latest match from the Riot API, saves it to `data/`, and automatically generates the HTML viewer.

### Step 2 — Regenerate HTML from saved data

```bash
python src/lol_html_viewer_auto.py
# or on Windows:
run.bat
```

### Options

```bash
# Skip CSV output
python src/lol_html_viewer_auto.py --no-csv

# Use a specific data directory
python src/lol_html_viewer_auto.py --dir path/to/dir
```

Output is saved to `output/out_TIMESTAMP.html`. Open it directly in your browser — no server needed.

---

## Project Structure

```
riftviz/
├── .env                         # API_KEY, PLATFORM, PUUID (gitignored)
├── run.bat                      # Windows shortcut
├── assets/
│   └── 00_champ.json            # Champion ID → display name mapping
├── src/
│   ├── match.py                 # Fetch match data from Riot API
│   └── lol_html_viewer_auto.py  # Generate the HTML viewer
├── data/                        # Match JSON files (gitignored)
└── output/                      # Generated HTML / CSV (gitignored)
```

---

## Queue Support

Currently targets **Swift Play (Queue ID: 1700)**.
Change `queue=1700` in `src/match.py` to support other queues.

---

## Disclaimer

> graph-lol isn't endorsed by Riot Games and doesn't reflect the views or opinions of Riot Games or anyone officially involved in producing or managing Riot Games properties. League of Legends and Riot Games are trademarks or registered trademarks of Riot Games, Inc.

Champion icons are loaded at runtime from the [Data Dragon CDN](https://developer.riotgames.com/docs/lol#data-dragon). No image assets are stored in this repository.

---

## License

MIT — applies to the original source code in this repository.
Riot Games assets and API data are subject to the [Riot Games Terms of Service](https://www.riotgames.com/en/terms-of-service).
