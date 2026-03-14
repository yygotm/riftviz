# riftviz

A local League of Legends match analysis tool that fetches data from the Riot Games API and generates a self-contained HTML viewer with interactive charts and a visual event timeline.

---

## Demo

<img width="1280" alt="Stats tables and KDA Breakdown" src="https://github.com/user-attachments/assets/ffded0fb-e692-4112-b331-7baec0be5b92" />
<img width="1280" alt="KDA Ratio / Damage / Gold charts" src="https://github.com/user-attachments/assets/0c3092f2-94df-4532-bc18-e9e6672710e3" />
<img width="1280" alt="CS / Vision / CC / Scatter plot" src="https://github.com/user-attachments/assets/4cd5ca11-8724-4e39-820f-6ad18c0dba48" />
<img width="1280" alt="Performance radar / KP / Dead Time" src="https://github.com/user-attachments/assets/43075911-bc24-47ee-8492-4a8533d27f31" />
<img width="1280" alt="Gold diff timeline" src="https://github.com/user-attachments/assets/dcf55ded-3c6b-4c7a-8976-d4dc8f7ae65d" />
<img width="1280" alt="Event timeline" src="https://github.com/user-attachments/assets/9dfccf4f-fa4d-48d3-a169-4bfeb5217f3e" />

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
# Swift Play (default)
python src/fetch_match_data.py

# Ranked Solo/Duo
python src/fetch_match_data.py --queue ranked-solo

# Ranked Flex
python src/fetch_match_data.py --queue ranked-flex
```

Pulls the latest match from the Riot API, saves it to `data/`, and automatically generates the HTML viewer.

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
├── build_viewer.bat             # Windows shortcut for HTML generation
├── src/
│   ├── fetch_match_data.py      # Fetch match data from Riot API
│   └── lol_html_viewer_auto.py  # Generate the HTML viewer
├── data/                        # Match JSON files (gitignored)
└── output/                      # Generated HTML / CSV (gitignored)
```

---

## Disclaimer

> riftviz isn't endorsed by Riot Games and doesn't reflect the views or opinions of Riot Games or anyone officially involved in producing or managing Riot Games properties. League of Legends and Riot Games are trademarks or registered trademarks of Riot Games, Inc.

Champion icons are loaded at runtime from the [Data Dragon CDN](https://developer.riotgames.com/docs/lol#data-dragon). No image assets are stored in this repository.

---

## License

MIT — applies to the original source code in this repository.
Riot Games assets and API data are subject to the [Riot Games Terms of Service](https://www.riotgames.com/en/terms-of-service).
