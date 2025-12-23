from __future__ import annotations

import os
import contextlib

from telegram import Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from app.storage.db import get_connection
from app.storage.repo import ReviewRepository, TransactionRepository
from app.telegram.core import TelegramCore
from app.telegram.messages import build_category_keyboard, build_review_message, build_status_message


class TelegramReviewBot(TelegramCore):
    def __init__(self, token: str, categories: list[str]):
        super().__init__(token)
        self._categories = categories
        self._allowed_chat_id = os.getenv("TELEGRAM_CHAT_ID")

    def set_handlers(self):
        self._app.add_handler(CommandHandler("start", self._cmd_start))
        self._app.add_handler(CommandHandler("help", self._cmd_help))
        self._app.add_handler(CallbackQueryHandler(self._on_callback))
        self._app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._on_text))

    async def _cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("Bot iniciado.")

    async def _cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "Use os botões para aprovar/editar/cancelar transações."
        )

    async def _on_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        q = update.callback_query
        await q.answer()

        if self._allowed_chat_id and str(update.effective_chat.id) != str(self._allowed_chat_id):
            return

        data = q.data or ""
        if data.startswith("APPROVE:"):
            review_id = int(data.split(":", 1)[1])
            await self._approve_review(review_id)
            await self._replace_message_with_status(
                q, review_id, "Confirmado ✅"
            )
            return
        if data.startswith("CANCEL:"):
            review_id = int(data.split(":", 1)[1])
            await self._cancel_review(review_id)
            await self._replace_message_with_status(
                q, review_id, "Cancelado ❌"
            )
            return
        if data.startswith("EDIT_CAT:"):
            review_id = int(data.split(":", 1)[1])
            kb = build_category_keyboard(review_id, self._categories)
            await self._replace_message_for_review(
                q,
                review_id,
                self._review_prompt_text(review_id, "Selecione a categoria:"),
                reply_markup=kb,
            )
            return
        if data.startswith("CAT:"):
            _, review_id_str, category = data.split(":", 2)
            review_id = int(review_id_str)
            await self._set_category(review_id, category)
            with contextlib.suppress(Exception):
                await q.message.delete()
            await self._send_review_message(update.effective_chat.id, review_id)
            return
        if data.startswith("CAT_CANCEL:"):
            review_id = int(data.split(":", 1)[1])
            with contextlib.suppress(Exception):
                await q.message.delete()
            await self._send_review_message(update.effective_chat.id, review_id)
            return
        if data.startswith("EDIT_DESC:"):
            review_id = int(data.split(":", 1)[1])
            await self._replace_message_for_review(
                q,
                review_id,
                self._review_prompt_text(
                    review_id, "Envie a nova descrição respondendo esta mensagem."
                ),
            )
            return

    async def _on_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if self._allowed_chat_id and str(update.effective_chat.id) != str(self._allowed_chat_id):
            return

        if not update.message.reply_to_message:
            return

        reply_msg = update.message.reply_to_message
        with get_connection() as conn:
            repo = ReviewRepository(conn)
            review = repo.get_review_by_message(
                str(update.effective_chat.id), str(reply_msg.message_id)
            )
            if not review or review.id is None:
                return
            review_id = review.id
        new_desc = update.message.text.strip()
        if not new_desc:
            return

        with get_connection() as conn:
            repo = ReviewRepository(conn)
            repo.update_review_final(
                review_id,
                new_desc,
                review.final_category or review.suggested_category,
                review.final_nickname or review.suggested_nickname,
            )

        with contextlib.suppress(Exception):
            await update.message.reply_to_message.delete()
            await update.message.delete()
        await self._send_review_message(update.effective_chat.id, review_id)

    async def _approve_review(self, review_id: int):
        with get_connection() as conn:
            repo = ReviewRepository(conn)
            review = repo.get_review(review_id)
            if not review:
                return
            final_desc = review.final_description or review.suggested_description
            final_cat = review.final_category or review.suggested_category
            final_nick = review.final_nickname or review.suggested_nickname
            repo.update_review_final(review_id, final_desc, final_cat, final_nick)
            repo.update_review_status(review_id, "approved")

    async def _cancel_review(self, review_id: int):
        with get_connection() as conn:
            repo = ReviewRepository(conn)
            repo.update_review_status(review_id, "cancelled")

    async def _set_category(self, review_id: int, category: str):
        with get_connection() as conn:
            repo = ReviewRepository(conn)
            review = repo.get_review(review_id)
            if not review:
                return
            repo.update_review_final(
                review_id,
                review.final_description or review.suggested_description,
                category,
                review.final_nickname or review.suggested_nickname,
            )

    async def _replace_message(self, query, text: str, reply_markup=None):
        with contextlib.suppress(Exception):
            await query.message.delete()
        await query.message.chat.send_message(text, reply_markup=reply_markup)

    async def _replace_message_for_review(
        self, query, review_id: int, text: str, reply_markup=None
    ):
        with contextlib.suppress(Exception):
            await query.message.delete()
        msg = await query.message.chat.send_message(text, reply_markup=reply_markup)
        with get_connection() as conn:
            repo = ReviewRepository(conn)
            repo.update_review_telegram(review_id, str(msg.chat_id), str(msg.message_id))

    async def _replace_message_with_status(self, query, review_id: int, status: str):
        with get_connection() as conn:
            review_repo = ReviewRepository(conn)
            tx_repo = TransactionRepository(conn)
            review = review_repo.get_review(review_id)
            if not review:
                return
            tx = tx_repo.get_transaction(review.mp_id)
            if not tx:
                return
            text = build_status_message(review, tx, status)

        with contextlib.suppress(Exception):
            await query.message.delete()
        await query.message.chat.send_message(text)

    async def _send_review_message(self, chat_id: int, review_id: int):
        with get_connection() as conn:
            review_repo = ReviewRepository(conn)
            tx_repo = TransactionRepository(conn)
            review = review_repo.get_review(review_id)
            if not review:
                return
            tx = tx_repo.get_transaction(review.mp_id)
            if not tx:
                return
            text, keyboard = build_review_message(review, tx)

        msg = await self._app.bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=keyboard,
        )
        with get_connection() as conn:
            review_repo = ReviewRepository(conn)
            review_repo.update_review_telegram(review_id, str(chat_id), str(msg.message_id))

    def _review_prompt_text(self, review_id: int, prompt: str) -> str:
        with get_connection() as conn:
            review_repo = ReviewRepository(conn)
            tx_repo = TransactionRepository(conn)
            review = review_repo.get_review(review_id)
            if not review:
                return prompt
            tx = tx_repo.get_transaction(review.mp_id)
            if not tx:
                return prompt
            text, _ = build_review_message(review, tx)
        return f"{text}\n\n{prompt}"
