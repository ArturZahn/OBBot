from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from app.domain.models import Review, Transaction


def _make_keyboard_for_review(review: Review) -> InlineKeyboardMarkup:
    if review.kind == "deposit":
        buttons = [
            InlineKeyboardButton("❌", callback_data=f"CANCEL:{review.id}"),
            InlineKeyboardButton("✅", callback_data=f"APPROVE:{review.id}"),
        ]
        return InlineKeyboardMarkup([buttons])

    buttons = [
        InlineKeyboardButton("Editar categoria", callback_data=f"EDIT_CAT:{review.id}"),
        InlineKeyboardButton("Editar descrição", callback_data=f"EDIT_DESC:{review.id}"),
        InlineKeyboardButton("❌", callback_data=f"CANCEL:{review.id}"),
        InlineKeyboardButton("✅", callback_data=f"APPROVE:{review.id}"),
    ]
    return InlineKeyboardMarkup([buttons[:2], buttons[2:]])


def _review_description(review: Review, transaction: Transaction) -> str:
    if review.final_description:
        return review.final_description
    if review.suggested_description:
        return review.suggested_description
    return f"Descrição pendente ({transaction.description})"


def _review_category(review: Review) -> str:
    return review.final_category or review.suggested_category or "Categoria pendente"


def _amount_display(transaction: Transaction, kind: str) -> float:
    if kind == "deposit":
        return transaction.amount
    amount = transaction.amount
    if transaction.direction == "in":
        return -amount
    return amount


def build_review_message(
    review: Review, transaction: Transaction
) -> tuple[str, InlineKeyboardMarkup]:
    description = _review_description(review, transaction)
    category = _review_category(review)
    amount = _amount_display(transaction, review.kind)
    amount_str = f"R$ {amount:.2f}"

    if review.kind == "deposit":
        text = (
            "💰 Depósito 💰\n"
            f"{amount_str} {review.suggested_nickname}\n\n"
            f"{transaction.description_primary}\n"
            f"{transaction.description_secondary}"
        )
    else:
        text = (
            "💸 Gasto 💸\n"
            f"{amount_str} {category}\n"
            f"{description}\n\n"
            f"{transaction.description_primary}\n"
            f"{transaction.description_secondary}"
        )

    return text, _make_keyboard_for_review(review)


def build_status_message(review: Review, transaction: Transaction, status: str) -> str:
    description = _review_description(review, transaction)
    category = _review_category(review)
    amount = _amount_display(transaction, review.kind)
    amount_str = f"R$ {amount:.2f}"

    if review.kind == "deposit":
        body = (
            "💰 Depósito 💰\n"
            f"{amount_str} {review.final_nickname or review.suggested_nickname}"
        )
    else:
        body = (
            "💸 Gasto 💸\n"
            f"{amount_str} {category}\n"
            f"{description}"
        )

    return f"{body}\n\n{status}"


def build_category_keyboard(review_id: int, categories: list[str]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for cat in categories:
        row.append(InlineKeyboardButton(cat, callback_data=f"CAT:{review_id}:{cat}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton("Cancelar", callback_data=f"CAT_CANCEL:{review_id}")])
    return InlineKeyboardMarkup(rows)
