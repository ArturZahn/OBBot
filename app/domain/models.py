from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Transaction:
    mp_id: str
    occurred_at: str
    amount: float
    direction: str
    description_primary: str
    description_secondary: str
    description: str
    raw_json: str | None = None

    @classmethod
    def from_scrape(
        cls,
        mp_id: str,
        occurred_at: str,
        amount_signed: float,
        description_primary: str,
        description_secondary: str,
    ) -> "Transaction":
        direction = "in" if amount_signed >= 0 else "out"
        amount = abs(amount_signed)
        description = f"{description_primary} {description_secondary}".strip()
        return cls(
            mp_id=mp_id,
            occurred_at=occurred_at,
            amount=amount,
            direction=direction,
            description_primary=description_primary,
            description_secondary=description_secondary,
            description=description,
        )


@dataclass(frozen=True)
class Review:
    id: int | None
    mp_id: str
    kind: str
    status: str
    suggested_description: str | None
    suggested_category: str | None
    suggested_nickname: str | None
    final_description: str | None
    final_category: str | None
    final_nickname: str | None
    telegram_chat_id: str | None
    telegram_message_id: str | None
    last_error: str | None
    created_at: str | None
    updated_at: str | None
