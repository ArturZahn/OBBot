from __future__ import annotations

import datetime as dt
import asyncio
import time
import threading
import sys

from dotenv import load_dotenv

from app.jobs.classify_job import run_classify_job
from app.jobs.review_job import run_review_job
from app.jobs.scrape_job import run_scrape_job
from app.jobs.telegram_bot import run_bot
from app.jobs.write_job import run_write_job

def _next_run_at(hour: int, minute: int) -> dt.datetime:
    now = dt.datetime.now()
    candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if candidate <= now:
        candidate = candidate + dt.timedelta(days=1)
    return candidate


def _stdin_watcher(trigger_evt: threading.Event) -> None:
    while True:
        line = sys.stdin.readline()
        if not line:
            time.sleep(0.1)
            continue
        trigger_evt.set()


def main() -> None:
    load_dotenv("data/.env")

    bot_thread = threading.Thread(target=run_bot, name="TelegramBotRunner", daemon=True)
    bot_thread.start()

    trigger_evt = threading.Event()
    watcher = threading.Thread(
        target=_stdin_watcher, args=(trigger_evt,), name="RunnerStdinWatcher", daemon=True
    )
    watcher.start()

    print("[runner] starting scrape_job on startup")
    try:
        scraped = run_scrape_job()
        print(f"[runner] scrape_job done: {scraped}")
        print("[runner] starting classify_job")
        classified = run_classify_job()
        print(f"[runner] classify_job done: classified={classified}")
        print("[runner] starting review_job")
        sent = asyncio.run(run_review_job())
        print(f"[runner] review_job done: sent={sent}")
    except Exception as exc:
        print(f"[runner] startup scrape/classify/review failed: {exc}")

    next_scrape = _next_run_at(22, 0)
    print(f"[runner] next scrape at {next_scrape}")

    try:
        while True:
            now = dt.datetime.now()
            if now >= next_scrape or trigger_evt.is_set():
                trigger_evt.clear()
                print("[runner] starting scrape_job")
                try:
                    scraped = run_scrape_job()
                    print(f"[runner] scrape_job done: {scraped}")
                    print("[runner] starting classify_job")
                    classified = run_classify_job()
                    print(f"[runner] classify_job done: classified={classified}")
                    print("[runner] starting review_job")
                    sent = asyncio.run(run_review_job())
                    print(f"[runner] review_job done: sent={sent}")
                except Exception as exc:
                    print(f"[runner] scrape/classify/review failed: {exc}")
                next_scrape = _next_run_at(22, 0)
                print(f"[runner] next scrape at {next_scrape}")

            try:
                written = run_write_job()
                if written:
                    print(f"[runner] write_job done: written={written}")
            except Exception as exc:
                print(f"[runner] write job failed: {exc}")

            trigger_evt.wait(timeout=30)
    finally:
        pass


if __name__ == "__main__":
    try:
        import os
        os.makedirs("oi", exist_ok=True)
        main()
    except KeyboardInterrupt:
        print("\n[runner] interrupted, exiting...")
