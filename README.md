# SAI Tipster — Powered by MiroFish

Serie A & Champions League AI prediction tool using multi-agent simulation.

---

## What This Does

1. Pulls live fixtures, standings, and statistics for **Serie A** and **Champions League**
2. Generates a rich match analysis report (form, xG, corners, cards, H2H)
3. Feeds the report into **MiroFish** as seed material
4. MiroFish runs a multi-agent simulation (analysts debating the match)
5. The ReportAgent produces structured predictions with probabilities for:
   - Match result (1X2)
   - Over/Under 2.5 and 3.5 goals
   - Both Teams To Score (BTTS)
   - Corners Over/Under
   - Yellow cards Over/Under
   - Red card probability

---

## Requirements

| Tool | Version | Download |
|------|---------|----------|
| Python | 3.11 or 3.12 | https://www.python.org/downloads/ |
| Node.js | 18+ | Already installed |
| uv | latest | https://docs.astral.sh/uv/getting-started/installation/ |

---

## Setup (One Time)

### Step 1 — Install Python 3.11
Download from https://www.python.org/downloads/
During install: **check "Add Python to PATH"**

### Step 2 — Install uv
Open PowerShell and run:
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### Step 3 — Get your API keys

**Groq API (free):**
1. Go to https://console.groq.com
2. Sign up (free, no credit card)
3. Create an API key
4. Copy it

**football-data.org (free):**
1. Go to https://www.football-data.org/client/register
2. Sign up (free)
3. Check your email for the API token

### Step 4 — Configure your environment
Copy `.env.example` to `.env` and fill in your keys:
```
GROQ_API_KEY=your_groq_key_here
FOOTBALL_DATA_API_KEY=your_football_data_key_here
```

### Step 5 — Run setup
Double-click `setup.bat` or run in terminal:
```cmd
setup.bat
```

This will:
- Download MiroFish automatically
- Apply all patches (Zep → local memory, Groq config)
- Install all Python and Node dependencies

---

## Daily Use

Double-click `start.bat` — this starts both backend and frontend.

Open your browser at: **http://localhost:3000**

Navigate to the **"Betting"** tab in the top menu.

---

## How Predictions Work

1. Pick an upcoming match from the fixture list
2. Click **"Predict"**
3. The app fetches all available stats, builds a match report, and sends it to MiroFish
4. MiroFish simulates 10 rounds of analyst debate (takes ~2–4 min)
5. Results appear as probability bars for each betting market

---

## Data Sources

| Source | What it provides | Auth |
|--------|-----------------|------|
| football-data.org | Fixtures, standings, results, teams | Free API key |
| FBref.com | Corners, cards, shots, xG per game | Public (scraped) |
| Understat.com | xG historical data for Serie A | Public (scraped) |

---

## Project Structure

```
betting-predictor/
├── setup.bat               ← one-click setup
├── start.bat               ← start the app
├── apply_patches.bat       ← patches MiroFish (run by setup.bat)
├── .env                    ← your API keys (create from .env.example)
├── mirofish/               ← MiroFish engine (downloaded by setup.bat)
├── football/               ← data pipeline
│   ├── football_data_api.py
│   ├── fbref_scraper.py
│   └── models.py
├── seed/
│   └── generator.py        ← match stats → simulation report
├── predictor/
│   ├── mirofish_client.py  ← controls MiroFish via HTTP API
│   └── result_parser.py    ← extracts betting signals from report
└── patches/                ← MiroFish customizations
    └── backend/app/services/
        └── local_zep.py    ← local memory (replaces Zep Cloud)
```
