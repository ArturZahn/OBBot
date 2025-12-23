from __future__ import annotations

import os
import time

from dotenv import load_dotenv

from app.sheets.client import SheetsClient
from app.sheets.service import SheetsService
from app.telegram.service import TelegramReviewBot


def run_bot() -> None:
    load_dotenv("data/.env")
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_TOKEN must be set.")

    spreadsheet_id = os.getenv("SHEETS_ID")
    credentials_file = os.getenv("GOOGLE_CREDENTIALS")
    categories: list[str] = []
    if spreadsheet_id and credentials_file:
        sheets = SheetsService(SheetsClient(spreadsheet_id, credentials_file))
        categories = sheets.get_categories()

    bot = TelegramReviewBot(token, categories)
    bot.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        bot.stop()


if __name__ == "__main__":
    run_bot()
