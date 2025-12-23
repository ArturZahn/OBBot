from __future__ import annotations

from app.scraper.client import MercadoPagoClient
from app.scraper.service import ScraperService
from app.storage.db import get_connection, init_db, resolve_db_path
from app.storage.repo import TransactionRepository


def run_scrape_job(max_pages: int = 1) -> tuple[int, int, str]:
    with get_connection() as conn:
        init_db(conn)
        repo = TransactionRepository(conn)
        with MercadoPagoClient(user_data_dir="data/browser_profile") as client:
            service = ScraperService(client)
            txs = service.scrape_transactions(max_pages=max_pages)
        inserted = repo.insert_transactions(txs)
    return len(txs), inserted, resolve_db_path()


if __name__ == "__main__":
    total, inserted, db_path = run_scrape_job()
    print(f"scraped={total} inserted={inserted} db={db_path}")
