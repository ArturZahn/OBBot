from __future__ import annotations

from dataclasses import dataclass

from app.domain.models import Transaction
from app.processing.rules import Classification, classify_transaction


@dataclass(frozen=True)
class ClassifiedTransaction:
    transaction: Transaction
    classification: Classification


def classify_transactions(
    transactions: list[Transaction], names_to_nicknames: dict[str, str]
) -> list[ClassifiedTransaction]:
    return [
        ClassifiedTransaction(t, classify_transaction(t, names_to_nicknames))
        for t in transactions
    ]
