from __future__ import annotations

import json
import re
import hashlib

import dateparser

from app.domain.models import Transaction

BRL_PATTERN = re.compile(
    r"""
    ^\s*
    (?P<prefix_sign>[+-]?)       # optional sign before “R$”
    \s*R\$\s*
    (?P<post_sign>[+-]?)         # optional sign right after “R$”
    (?P<int>\d{1,3}(?:\.\d{3})*) # integer part with optional thousands dots
    ,
    (?P<dec>\d{2})               # exactly two centavos
    \s*$
    """,
    re.VERBOSE,
)


def convert_brl_format(text: str) -> float:
    m = BRL_PATTERN.match(text)
    if not m:
        raise ValueError("Balance format not recognized.")

    prefix, post = m["prefix_sign"], m["post_sign"]
    if prefix and post:
        raise ValueError("Conflicting signs in balance string.")

    sign = -1 if (prefix == "-" or post == "-") else 1
    integer_part = m["int"].replace(".", "")
    cents_part = m["dec"]
    return sign * float(f"{integer_part}.{cents_part}")


def convert_relative_date(date_text: str) -> str:
    dt = dateparser.parse(
        date_text,
        languages=["pt"],
        settings={"TIMEZONE": "UTC", "RETURN_AS_TIMEZONE_AWARE": False},
    )
    if dt is None:
        raise ValueError("Date parsing failed.")
    return dt.strftime("%Y-%m-%d")


def _normalize_time(time_text: str) -> str:
    time_text = time_text.strip()
    if not time_text:
        return "00:00"
    return ":".join(time_text.split("h"))

def _normalize_description(text: str) -> str:
    return " ".join(text.split()).strip().lower()


def _build_mp_id(
    occurred_at: str,
    amount_signed: float,
    description_primary: str,
    description_secondary: str,
) -> str:
    # Deterministic ID based on stable fields to avoid row index drift.
    payload = "|".join(
        [
            occurred_at,
            f"{amount_signed:.2f}",
            _normalize_description(description_primary),
            _normalize_description(description_secondary),
        ]
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return f"{occurred_at}:{digest}"


def parse_transactions_page(page) -> list[Transaction]:

    days_el = page.locator(".binnacle-list .binnacle-rows-wrapper")
    if days_el.count() == 0:
        raise ValueError("No transactions found; page structure may have changed.")

    transactions: list[Transaction] = []

    for i in range(days_el.count()):
        day_el = days_el.nth(i)
        day_text = day_el.locator(
            ".binnacle-rows-wrapper__header .binnacle-rows-wrapper__title"
        ).text_content()

        day_date = convert_relative_date(day_text)

        rows_el = day_el.locator(".binnacle-row")
        day_rows: list[dict[str, str]] = []
        for j in range(rows_el.count()):
            row_el = rows_el.nth(j)
            description_primary = row_el.locator(
                ".andes-list__item-first-column .andes-list__item-primary .binnacle-row__title"
            ).text_content()

            sec_locator = row_el.locator(
                ".andes-list__item-first-column .andes-list__item-secondary"
            )
            description_secondary = sec_locator.text_content() if sec_locator.count() else ""

            amount_text = row_el.locator(
                ".andes-list__item-second-column .andes-money-amount"
            ).text_content()
            time_text = row_el.locator(
                ".andes-list__item-second-column .binnacle-row__time"
            ).text_content()

            amount_signed = convert_brl_format(amount_text)
            time_value = _normalize_time(time_text)
            occurred_at = f"{day_date} {time_value}"

            raw_payload = {
                "day_date": day_date,
                "time": time_value,
                "amount_text": amount_text,
                "description_primary": description_primary,
                "description_secondary": description_secondary,
            }
            day_rows.insert(
                0,
                {
                    "occurred_at": occurred_at,
                    "amount_signed": amount_signed,
                    "description_primary": description_primary,
                    "description_secondary": description_secondary,
                    "raw_json": json.dumps(raw_payload),
                },
            )

        for idx, row in enumerate(day_rows, start=1):
            transaction = Transaction.from_scrape(
                mp_id=_build_mp_id(
                    occurred_at=row["occurred_at"],
                    amount_signed=row["amount_signed"],
                    description_primary=row["description_primary"],
                    description_secondary=row["description_secondary"],
                ),
                occurred_at=row["occurred_at"],
                amount_signed=row["amount_signed"],
                description_primary=row["description_primary"],
                description_secondary=row["description_secondary"],
            )
            transactions.append(
                Transaction(
                    mp_id=transaction.mp_id,
                    occurred_at=transaction.occurred_at,
                    amount=transaction.amount,
                    direction=transaction.direction,
                    description_primary=transaction.description_primary,
                    description_secondary=transaction.description_secondary,
                    description=transaction.description,
                    raw_json=row["raw_json"],
                )
            )

    transactions.sort(key=lambda t: t.occurred_at)
    return transactions
