from __future__ import annotations

import os
import asyncio

from telegram import Bot

from dotenv import load_dotenv

from app.storage.db import get_connection, init_db
from app.storage.repo import ReviewRepository, TransactionRepository
from app.telegram.messages import build_review_message


async def run_review_job(limit: int = 50) -> int:
    load_dotenv("data/.env")
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        raise RuntimeError("TELEGRAM_TOKEN and TELEGRAM_CHAT_ID must be set.")

    bot = Bot(token=token)

    with get_connection() as conn:
        init_db(conn)
        review_repo = ReviewRepository(conn)
        tx_repo = TransactionRepository(conn)

        reviews = review_repo.list_reviews_by_status("pending_send", limit)
        for review in reviews:
            tx = tx_repo.get_transaction(review.mp_id)
            if not tx:
                review_repo.update_review_error(review.id, "Transaction not found.")
                review_repo.update_review_status(review.id, "failed")
                continue

            text, keyboard = build_review_message(review, tx)
            try:
                msg = await bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    reply_markup=keyboard,
                )
            except Exception as exc:  # pragma: no cover - network dependency
                review_repo.update_review_error(review.id, str(exc))
                continue

            review_repo.update_review_telegram(review.id, str(chat_id), str(msg.message_id))
            review_repo.update_review_status(review.id, "awaiting_user")

        return len(reviews)


if __name__ == "__main__":
    sent = asyncio.run(run_review_job())
    print(f"sent={sent}")
