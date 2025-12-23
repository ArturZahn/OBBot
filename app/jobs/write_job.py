from __future__ import annotations

import os

from dotenv import load_dotenv

from app.processing.date_utils import iso_datetime_to_dmy
from app.sheets.client import SheetsClient
from app.sheets.service import SheetsService
from app.storage.db import get_connection, init_db
from app.storage.repo import ReviewRepository, TransactionRepository


def run_write_job(limit: int = 50) -> int:
    load_dotenv("data/.env")
    spreadsheet_id = os.getenv("SHEETS_ID")
    credentials_file = os.getenv("GOOGLE_CREDENTIALS")
    if not spreadsheet_id or not credentials_file:
        raise RuntimeError("SHEETS_ID and GOOGLE_CREDENTIALS must be set.")

    sheets = SheetsService(SheetsClient(spreadsheet_id, credentials_file))

    with get_connection() as conn:
        init_db(conn)
        review_repo = ReviewRepository(conn)
        tx_repo = TransactionRepository(conn)

        reviews = review_repo.list_reviews_by_status("approved", limit)
        for review in reviews:
            tx = tx_repo.get_transaction(review.mp_id)
            if not tx:
                review_repo.update_review_error(review.id, "Transaction not found.")
                review_repo.update_review_status(review.id, "failed")
                continue

            date_dmy = iso_datetime_to_dmy(tx.occurred_at)
            if review.kind == "deposit":
                nickname = review.final_nickname or review.suggested_nickname
                if not nickname:
                    review_repo.update_review_error(review.id, "Missing nickname.")
                    review_repo.update_review_status(review.id, "failed")
                    continue
                sheets.insert_deposit(nickname, date_dmy, tx.amount)
            else:
                description = review.final_description or review.suggested_description
                category = review.final_category or review.suggested_category
                if not description or not category:
                    review_repo.update_review_error(review.id, "Missing description/category.")
                    review_repo.update_review_status(review.id, "failed")
                    continue
                amount = tx.amount if tx.direction == "out" else -tx.amount
                sheets.insert_spent(date_dmy, amount, description, category)

            review_repo.update_review_status(review.id, "written")
            tx_repo.set_status(tx.mp_id, "sent")

        return len(reviews)


if __name__ == "__main__":
    count = run_write_job()
    print(f"written={count}")
