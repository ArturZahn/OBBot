from __future__ import annotations

import sqlite3
from typing import Iterable

from app.domain.models import Review, Transaction


class TransactionRepository:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def insert_transactions(self, transactions: Iterable[Transaction]) -> int:
        rows = [
            (
                t.mp_id,
                t.occurred_at,
                t.amount,
                t.direction,
                t.description_primary,
                t.description_secondary,
                t.description,
                t.raw_json,
            )
            for t in transactions
        ]
        if not rows:
            return 0
        cur = self._conn.executemany(
            """
            INSERT OR IGNORE INTO transactions
                (mp_id, occurred_at, amount, direction, description_primary, description_secondary, description, raw_json)
            VALUES
                (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        self._conn.commit()
        return cur.rowcount or 0

    def get_pending_transactions(self, limit: int = 50) -> list[Transaction]:
        return self.get_transactions_by_status("new", limit)

    def get_transactions_by_status(self, status: str, limit: int = 50) -> list[Transaction]:
        cur = self._conn.execute(
            """
            SELECT mp_id, occurred_at, amount, direction, description_primary, description_secondary, description, raw_json
            FROM transactions
            WHERE status = ?
            ORDER BY occurred_at ASC
            LIMIT ?
            """,
            (status, limit),
        )
        return [
            Transaction(
                mp_id=row["mp_id"],
                occurred_at=row["occurred_at"],
                amount=row["amount"],
                direction=row["direction"],
                description_primary=row["description_primary"],
                description_secondary=row["description_secondary"],
                description=row["description"] or "",
                raw_json=row["raw_json"],
            )
            for row in cur.fetchall()
        ]

    def set_status(self, mp_id: str, status: str) -> None:
        self._conn.execute(
            """
            UPDATE transactions
            SET status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE mp_id = ?
            """,
            (status, mp_id),
        )
        self._conn.commit()

    def set_status_batch(self, mp_ids: Iterable[str], status: str) -> int:
        ids = list(mp_ids)
        if not ids:
            return 0
        cur = self._conn.executemany(
            """
            UPDATE transactions
            SET status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE mp_id = ?
            """,
            [(status, mp_id) for mp_id in ids],
        )
        self._conn.commit()
        return cur.rowcount or 0

    def get_transaction(self, mp_id: str) -> Transaction | None:
        cur = self._conn.execute(
            """
            SELECT mp_id, occurred_at, amount, direction, description_primary, description_secondary, description, raw_json
            FROM transactions
            WHERE mp_id = ?
            """,
            (mp_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        return Transaction(
            mp_id=row["mp_id"],
            occurred_at=row["occurred_at"],
            amount=row["amount"],
            direction=row["direction"],
            description_primary=row["description_primary"],
            description_secondary=row["description_secondary"],
            description=row["description"] or "",
            raw_json=row["raw_json"],
        )

    def mark_sent_batch(self, mp_ids: Iterable[str]) -> int:
        ids = list(mp_ids)
        if not ids:
            return 0
        cur = self._conn.executemany(
            """
            UPDATE transactions
            SET status = 'sent', updated_at = CURRENT_TIMESTAMP
            WHERE mp_id = ?
            """,
            [(mp_id,) for mp_id in ids],
        )
        self._conn.commit()
        return cur.rowcount or 0

    def mark_failed(self, mp_id: str, error: str) -> None:
        self._conn.execute(
            """
            UPDATE transactions
            SET status = 'failed',
                attempts = attempts + 1,
                last_error = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE mp_id = ?
            """,
            (error, mp_id),
        )
        self._conn.commit()

    def mark_failed_batch(self, mp_ids: Iterable[str], error: str) -> int:
        ids = list(mp_ids)
        if not ids:
            return 0
        cur = self._conn.executemany(
            """
            UPDATE transactions
            SET status = 'failed',
                attempts = attempts + 1,
                last_error = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE mp_id = ?
            """,
            [(error, mp_id) for mp_id in ids],
        )
        self._conn.commit()
        return cur.rowcount or 0

    def load_state(self, key: str) -> str | None:
        cur = self._conn.execute("SELECT value FROM state WHERE key = ?", (key,))
        row = cur.fetchone()
        return row["value"] if row else None

    def save_state(self, key: str, value: str) -> None:
        self._conn.execute(
            """
            INSERT INTO state (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )
        self._conn.commit()


class ReviewRepository:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def create_review(self, review: Review) -> int:
        cur = self._conn.execute(
            """
            INSERT INTO reviews (
                mp_id,
                kind,
                status,
                suggested_description,
                suggested_category,
                suggested_nickname,
                final_description,
                final_category,
                final_nickname,
                telegram_chat_id,
                telegram_message_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                review.mp_id,
                review.kind,
                review.status,
                review.suggested_description,
                review.suggested_category,
                review.suggested_nickname,
                review.final_description,
                review.final_category,
                review.final_nickname,
                review.telegram_chat_id,
                review.telegram_message_id,
            ),
        )
        self._conn.commit()
        return int(cur.lastrowid)

    def update_review_status(self, review_id: int, status: str) -> None:
        self._conn.execute(
            """
            UPDATE reviews
            SET status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (status, review_id),
        )
        self._conn.commit()

    def update_review_telegram(
        self, review_id: int, chat_id: str, message_id: str
    ) -> None:
        self._conn.execute(
            """
            UPDATE reviews
            SET telegram_chat_id = ?, telegram_message_id = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (chat_id, message_id, review_id),
        )
        self._conn.commit()

    def update_review_final(
        self,
        review_id: int,
        final_description: str | None,
        final_category: str | None,
        final_nickname: str | None,
    ) -> None:
        self._conn.execute(
            """
            UPDATE reviews
            SET final_description = ?, final_category = ?, final_nickname = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (final_description, final_category, final_nickname, review_id),
        )
        self._conn.commit()

    def update_review_error(self, review_id: int, error: str) -> None:
        self._conn.execute(
            """
            UPDATE reviews
            SET last_error = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (error, review_id),
        )
        self._conn.commit()

    def list_reviews_by_status(self, status: str, limit: int = 50) -> list[Review]:
        cur = self._conn.execute(
            """
            SELECT id, mp_id, kind, status, suggested_description, suggested_category,
                   suggested_nickname, final_description, final_category, final_nickname,
                   telegram_chat_id, telegram_message_id, last_error, created_at, updated_at
            FROM reviews
            WHERE status = ?
            ORDER BY created_at ASC
            LIMIT ?
            """,
            (status, limit),
        )
        return [self._row_to_review(row) for row in cur.fetchall()]

    def get_review(self, review_id: int) -> Review | None:
        cur = self._conn.execute(
            """
            SELECT id, mp_id, kind, status, suggested_description, suggested_category,
                   suggested_nickname, final_description, final_category, final_nickname,
                   telegram_chat_id, telegram_message_id, last_error, created_at, updated_at
            FROM reviews
            WHERE id = ?
            """,
            (review_id,),
        )
        row = cur.fetchone()
        return self._row_to_review(row) if row else None

    def get_review_by_message(self, chat_id: str, message_id: str) -> Review | None:
        cur = self._conn.execute(
            """
            SELECT id, mp_id, kind, status, suggested_description, suggested_category,
                   suggested_nickname, final_description, final_category, final_nickname,
                   telegram_chat_id, telegram_message_id, last_error, created_at, updated_at
            FROM reviews
            WHERE telegram_chat_id = ? AND telegram_message_id = ?
            """,
            (chat_id, message_id),
        )
        row = cur.fetchone()
        return self._row_to_review(row) if row else None

    def _row_to_review(self, row: sqlite3.Row) -> Review:
        return Review(
            id=row["id"],
            mp_id=row["mp_id"],
            kind=row["kind"],
            status=row["status"],
            suggested_description=row["suggested_description"],
            suggested_category=row["suggested_category"],
            suggested_nickname=row["suggested_nickname"],
            final_description=row["final_description"],
            final_category=row["final_category"],
            final_nickname=row["final_nickname"],
            telegram_chat_id=row["telegram_chat_id"],
            telegram_message_id=row["telegram_message_id"],
            last_error=row["last_error"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
