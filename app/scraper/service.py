from __future__ import annotations

from datetime import datetime

from app.domain.models import Transaction
from app.scraper.client import MercadoPagoClient
from app.scraper.parser import parse_transactions_page


class ScraperService:
    def __init__(self, client: MercadoPagoClient) -> None:
        self._client = client

    def scrape_transactions(
        self,
        max_pages: int = 1,
        min_date: str | None = None,
    ) -> list[Transaction]:
        self._client.goto_home()
        self._client.ensure_logged_in()

        cutoff = None
        if min_date:
            cutoff = datetime.strptime(min_date, "%Y-%m-%d").date()

        transactions: list[Transaction] = []
        for page_number in range(1, max_pages + 1):
            self._client.goto_movements(page_number if page_number > 1 else None)
            page_transactions = parse_transactions_page(self._client.page)
            if not page_transactions:
                break

            if cutoff:
                filtered = []
                for transaction in page_transactions:
                    date_part = transaction.occurred_at.split(" ")[0]
                    if datetime.strptime(date_part, "%Y-%m-%d").date() < cutoff:
                        continue
                    filtered.append(transaction)
                page_transactions = filtered

            transactions.extend(page_transactions)
            if cutoff and len(page_transactions) == 0:
                break

        # import time
        # print("Scraping finished, sleeping to allow graceful browser close...")
        # time.sleep(10000)

        transactions.sort(key=lambda t: t.occurred_at)
        return transactions
