# OBBot

Mercado Pago scraper that stores transactions in SQLite, classifies them, asks for Telegram confirmation, and writes to Google Sheets. It is designed to run continuously and safely resume after restarts.

## Architecture
- Scraper collects transactions and stores them in SQLite (`data/db/transactions.db`).
- Classifier decides: deposit, spent, or ignore.
- Telegram review asks for confirmation/edits/cancel.
- Writer appends approved items to Google Sheets.

## Requirements
- Python 3.10+
- Playwright (Chromium)
- Google Sheets service account JSON
- Telegram bot token and chat id

## Setup
1) Create and activate a venv:
```bash
python3 -m venv .venv
source .venv/bin/activate
```

2) Install dependencies:
```bash
pip install playwright python-dotenv gspread oauth2client python-telegram-bot==20.7 dateparser
python -m playwright install --with-deps
```

3) Configure secrets in `data/.env`:
```env
SHEETS_ID=...
GOOGLE_CREDENTIALS=data/google_sheet_key.json
TELEGRAM_TOKEN=...
TELEGRAM_CHAT_ID=...
```

4) Copy Google credentials:
```bash
cp /path/to/google_sheet_key.json data/google_sheet_key.json
```

## Login (required once)
You must log into Mercado Pago to create the browser profile used by the scraper.

On a machine with a GUI:
```bash
python3 login.py
```
This opens a browser so you can log in and pass any CAPTCHAs. The login data is stored in `data/browser_profile`.

If you run the scraper on a headless server, do the login on a GUI machine and then copy `data/browser_profile` to the server.

## Running
### Single run (manual)
```bash
python -m app.jobs.scrape_job
python -m app.jobs.classify_job
python -m app.jobs.review_job
python -m app.jobs.write_job
```

### Bot (interactive)
```bash
python -m app.jobs.telegram_bot
```

### Continuous runner (recommended)
```bash
python -m app.jobs.runner
```
The runner:
- starts the Telegram bot
- runs scrape + classify + review on startup
- runs scrape + classify + review daily at 22:00
- runs write job every 30s
- supports manual trigger by pressing Enter

## Browser mode
Mercado Pago blocks headless. The scraper always runs headed.
On headless servers, use Xvfb:
```bash
xvfb-run -a python -m app.jobs.runner
```

## Docker
Build:
```bash
docker build -t obbot .
```

Run (using live project folder and .env):
```bash
docker run -it --rm -v "$PWD:/app" -w /app --env-file data/.env obbot
```

For convenience, those commands are in the docker_build.sh and docker_run.sh scripts.

Notes:
- The container runs `xvfb-run` by default to support headed Chromium.
- You can override env vars with `--env` or `--env-file`.

## Data locations
- Browser profile: `data/browser_profile`
- SQLite DB: `data/db/transactions.db`
- Env config: `data/.env`
