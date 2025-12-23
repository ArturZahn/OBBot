from __future__ import annotations

from playwright.sync_api import sync_playwright

import time

class MercadoPagoClient:
    def __init__(
        self,
        user_data_dir: str = "mp_profile",
        headless: bool = False,
        slow_mo_ms: int | None = None,
    ) -> None:
        self._user_data_dir = user_data_dir
        self._headless = headless
        self._slow_mo_ms = slow_mo_ms
        self._playwright = None
        self._context = None
        self._page = None

    def __enter__(self) -> "MercadoPagoClient":
        self._playwright = sync_playwright().start()
        self._context = self._playwright.chromium.launch_persistent_context(
            user_data_dir=self._user_data_dir,
            headless=self._headless,
            slow_mo=self._slow_mo_ms,
            args=["--disable-blink-features=AutomationControlled"],
            ignore_default_args=["--enable-automation"],
        )
        self._page = self._context.new_page()
        self._page.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', { get: () => false });"
        )
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._context:
            self._context.close()
        if self._playwright:
            self._playwright.stop()

    @property
    def page(self):
        if self._page is None:
            raise RuntimeError("Client not started. Use as a context manager.")
        return self._page

    def goto_home(self) -> None:
        self.page.goto("https://www.mercadopago.com.br/home")
        self.page.wait_for_load_state("load")

    def goto_movements(self, page_number: int | None = None) -> None:
        url = "https://www.mercadopago.com.br/banking/balance/movements"
        if page_number:
            url = f"{url}?page={page_number}"
        self.page.goto(url)
        self.page.wait_for_load_state("load")

    def ensure_logged_in(self) -> None:
        if self.page.locator(
            'text={"message":"local_rate_limited","status":429}'
        ).count():
            raise ValueError("Too many requests.")
        if self.page.locator("text=Iniciar sess\u00e3o").count():
            raise ValueError("Login required. Run the login flow first.")
        # if not self.page.locator("text=Sua \u00faltima atividade").count():
        if not self.page.locator("text=ltimas atividades").count():
            time.sleep(2000)
            # raise ValueError("Login state unknown; page may have changed.")
