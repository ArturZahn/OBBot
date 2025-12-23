from __future__ import annotations

import os

from dotenv import load_dotenv

from app.processing.classifier import classify_transactions
from app.storage.db import get_connection, init_db
from app.storage.repo import ReviewRepository, TransactionRepository
from app.sheets.client import SheetsClient
from app.sheets.service import SheetsService
from app.domain.models import Review


def run_classify_job(limit: int = 50) -> int:
    load_dotenv("data/.env")
    spreadsheet_id = os.getenv("SHEETS_ID")
    credentials_file = os.getenv("GOOGLE_CREDENTIALS")
    if not spreadsheet_id or not credentials_file:
        raise RuntimeError("SHEETS_ID and GOOGLE_CREDENTIALS must be set.")

    sheets = SheetsService(SheetsClient(spreadsheet_id, credentials_file))
    names_to_nicknames = sheets.get_payment_names()

    with get_connection() as conn:
        init_db(conn)
        tx_repo = TransactionRepository(conn)
        review_repo = ReviewRepository(conn)

        transactions = tx_repo.get_transactions_by_status("new", limit)
        classified = classify_transactions(transactions, names_to_nicknames)

        for item in classified:
            mp_id = item.transaction.mp_id
            if item.classification.kind == "ignore":
                tx_repo.set_status(mp_id, "ignored")
                continue

            review = Review(
                id=None,
                mp_id=mp_id,
                kind=item.classification.kind,
                status="pending_send",
                suggested_description=item.classification.suggested_description,
                suggested_category=item.classification.suggested_category,
                suggested_nickname=item.classification.suggested_nickname,
                final_description=None,
                final_category=None,
                final_nickname=None,
                telegram_chat_id=None,
                telegram_message_id=None,
                last_error=None,
                created_at=None,
                updated_at=None,
            )
            review_repo.create_review(review)
            tx_repo.set_status(mp_id, "classified")

        return len(classified)


if __name__ == "__main__":
    count = run_classify_job()
    print(f"classified={count}")
