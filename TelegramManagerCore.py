
import asyncio
import threading

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

class TelegramManagerCore:
    def __init__(self, token: str):
        self._token = token
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._app: Application | None = None
        self._ready_evt = threading.Event()
        self._stop_evt: asyncio.Event | None = None  # created inside bot loop

    def set_handlers(self):
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement set_handlers(self)"
        )

    # --- async bot main (runs inside the bot thread loop) ---
    async def _bot_main(self):
        self._app = Application.builder().token(self._token).build()

        self.set_handlers()

        self._stop_evt = asyncio.Event()

        # manual lifecycle instead of run_polling()
        await self._app.initialize()
        await self._app.start()
        await self._app.updater.start_polling()  # v20 async API

        self._ready_evt.set()  # let start() return

        # wait for stop() to signal
        await self._stop_evt.wait()

        # graceful shutdown
        await self._app.updater.stop()
        await self._app.stop()
        await self._app.shutdown()

    def _thread_target(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._bot_main())
        finally:
            self._loop.run_until_complete(self._loop.shutdown_asyncgens())
            self._loop.close()

    def start(self):
        if self._thread and self._thread.is_alive():
            print("Bot already running.")
            return
        self._thread = threading.Thread(
            target=self._thread_target, name="TelegramBotThread", daemon=True
        )
        self._thread.start()
        self._ready_evt.wait()
        print("Bot thread started.")

    def stop(self, timeout: float = 10.0):
        if not (self._loop and self._thread and self._thread.is_alive()):
            print("Bot not running.")
            return

        def _signal():
            if self._stop_evt and not self._stop_evt.is_set():
                self._stop_evt.set()

        self._loop.call_soon_threadsafe(_signal)
        self._thread.join(timeout=timeout)
        if self._thread.is_alive():
            print("Bot thread did not exit within timeout.") # warning
        else:
            print("Bot thread stopped cleanly.")

    def run_coroutine_threadsafe(self, coro, wait=False):
        if not (self._loop and self._thread and self._thread.is_alive()):
            raise RuntimeError("Bot loop is not running")

        fut = asyncio.run_coroutine_threadsafe(
            coro,
            self._loop
        )

        if wait:
            return fut.result()
        return fut