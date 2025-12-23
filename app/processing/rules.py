from __future__ import annotations

from dataclasses import dataclass

from app.domain.models import Transaction
from app.processing.name_utils import encode_name

DEPOSIT_PREFIXES = {"Transferência Pix recebida", "Transferência recebida"}


@dataclass(frozen=True)
class Classification:
    kind: str  # deposit | spent | ignore
    suggested_description: str | None
    suggested_category: str | None
    suggested_nickname: str | None


def _classify_spent(
    desc1: str, desc2: str, amount: float, names_to_nicknames: dict[str, str]
) -> tuple[str | None, str | None]:
    description = None
    category = None

    desc2_enc = encode_name(desc2)

    if desc1 == "Dinheiro reservado":
        if desc2_enc == "13 oseias":
            description = "Reservado para 13° Oséias"
            category = "Oséas"
        else:
            description = f"Reservado em '{desc2}'"
            category = "Caixinha"
    elif desc1 == "Dinheiro retirado":
        if desc2_enc == "13 oseias":
            description = "Retidado para 13° Oséias"
            category = "Oséas"
        else:
            description = f"Retirado de '{desc2}'"
            category = "Caixinha"
    elif desc1 == "Transferência enviada":
        if desc2_enc == "tenda atacado sa":
            description = "Compra tenda"
            category = "Mercado geral"
    elif desc1 == "Transferência Pix enviada":
        if desc2_enc == "oseas dias da silva selvagio":
            description = "Salário Oséas"
            category = "Oséas"
        elif desc2_enc == "walterdisney lima santos":
            description = "Pagamento vigia"
            category = "Vigia"
    elif desc1 == "Pagamento com QR Pix":
        if desc2_enc == "tenda atacado sa":
            description = "Compra tenda"
            category = "Mercado geral"
        elif desc2_enc == "companhia paulista de forca e luz":
            description = "Pagamento conta de luz"
            category = "Luz"
        elif desc2_enc == "telefonica brasil s a":
            description = "Pagamento conta de internet"
            category = "Internet"
        elif desc2_enc == "supermercados jau serve ltda":
            description = "o que foi comprado no jau?"
    elif desc1 == "Pagamento":
        if desc2_enc == "varejao passarinh":
            description = "compra no passarinho"
            category = "Mercado geral"
        elif desc2_enc == "jau serve lj 32":
            description = "o que foi comprado no jau?"
    elif desc1 == "Reserva programada":
        if desc2_enc == "13 oseias":
            description = "Reservado para 13° Oséias"
            category = "Oséas"
    elif desc1 == "Pagamento de contas":
        if desc2_enc == "saae sao carlos sp":
            description = "Pagamento conta de água"
            category = "Água"
        elif desc2_enc == "rfb - doc arrec emp":
            description = "Imposrto oséias"
            category = "Oséas"
        elif desc2_enc == "vivo movel sp":
            description = "Pagamento conta de internet"
            category = "Internet"
        elif desc2_enc == "cpfl paulista":
            description = "Pagamento conta de luz"
            category = "Luz"

    if description is None:
        if desc1 in {"Transferência enviada", "Transferência Pix enviada"}:
            if desc2_enc in names_to_nicknames and amount >= 3000:
                description = "Para sacar aluguel"
                category = "Aluguel marcos"

    if description is None:
        description = f"{desc1}: {desc2}"

    return description, category


def classify_transaction(
    transaction: Transaction, names_to_nicknames: dict[str, str]
) -> Classification:
    desc1 = transaction.description_primary
    desc2 = transaction.description_secondary

    if desc1 == "Rendimentos":
        return Classification(
            kind="ignore",
            suggested_description=None,
            suggested_category=None,
            suggested_nickname=None,
        )

    if transaction.direction == "in" and desc1 in DEPOSIT_PREFIXES:
        encoded = encode_name(desc2)
        nickname = names_to_nicknames.get(encoded)
        if nickname:
            return Classification(
                kind="deposit",
                suggested_description="Depósito na conta da casa",
                suggested_category="Depósito",
                suggested_nickname=nickname,
            )

    if transaction.direction in {"in", "out"}:
        description, category = _classify_spent(
            desc1=desc1,
            desc2=desc2,
            amount=transaction.amount,
            names_to_nicknames=names_to_nicknames,
        )
        classification = Classification(
            kind="spent",
            suggested_description=description,
            suggested_category=category,
            suggested_nickname=None,
        )
        if classification.suggested_category == "Rendimento":
            return Classification(
                kind="ignore",
                suggested_description=None,
                suggested_category=None,
                suggested_nickname=None,
            )
        return classification

    return Classification(
        kind="ignore",
        suggested_description=None,
        suggested_category=None,
        suggested_nickname=None,
    )
