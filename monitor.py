import threading
import time
from typing import Any, Callable
from playwright.sync_api import sync_playwright
import re, dateparser
from pyvirtualdisplay import Display

from configs import ConfigManager
import helper_functions

HIDE_WINDOW = False

CONFIG_FILE_PATH = "data/mp_scraper_config.json"
DEFAUTL_CONFIG = {
    "last_transaction_id": None
}

class PageMonitor:
    def __init__(self, refresh_period_in_sec):
        # self.interval    = 2
        self._thread     = threading.Thread(target=self._run, daemon=True)
        self._stop       = threading.Event()
        self.refresh_period = refresh_period_in_sec*1000

    def set_on_new_data(self, on_new_data):
        self.on_new_data = on_new_data

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop.set()
        self._thread.join()

    def _run(self):

        # # testing:
        # time.sleep(2)
        # data = [
        #     {'day_date': '2025-07-25', 'day_partial_balance': 1748.84, 'transactions': [{'description_primary': 'Rendimentos', 'description_secondary': '', 'amount': 100, 'time': '07:00'}]},
        #     {'day_date': '2025-08-01', 'day_partial_balance': 1748.84, 'transactions': [{'description_primary': 'Transferência recebida', 'description_secondary': 'Artur Zahn', 'amount': 4.0, 'time': '00:33'}, {'description_primary': 'Transferência recebida', 'description_secondary': 'Artur Zahn', 'amount': 4.0, 'time': '00:33'}, {'description_primary': 'Transferência recebida', 'description_secondary': 'ninguem', 'amount': 5.0, 'time': '00:33'}, {'description_primary': 'Rendimentos', 'description_secondary': '', 'amount': 0.79, 'time': '07:00'}, {'description_primary': 'Rendimentos', 'description_secondary': '', 'amount': 1, 'time': '07:00'}]},
        #     {'day_date': '2025-08-02', 'day_partial_balance': 1748.84, 'transactions': [{'description_primary': 'Rendimentos', 'description_secondary': '', 'amount': 10, 'time': '07:00'}]},
        # ]
        
        # try:
        #     self.on_new_data(data)
        # except Exception as e:
        #     print(f"Error in on_new_data handler: {e}")
        
        # while not self._stop.is_set():
        #     time.sleep(1)
        # return

        if HIDE_WINDOW:
            display = Display(visible=0, size=(200, 100))
            display.start()

        cfg = ConfigManager(CONFIG_FILE_PATH, DEFAUTL_CONFIG)
        cfg.load()

        refresh_period = self.refresh_period

        print("Iniciando navegador...")
        with sync_playwright() as p:
            ctx = p.chromium.launch_persistent_context(
                user_data_dir="mp_profile",
                headless=False,
                args=["--disable-blink-features=AutomationControlled"],ignore_default_args=["--enable-automation"]
            )
            page = ctx.new_page()
            page.add_init_script("""
              Object.defineProperty(navigator, 'webdriver', { get: () => false });
            """)
            page.goto("https://www.mercadopago.com.br/home")

            page.wait_for_load_state("load")
            print("Página carregada, verificando login...")
            try:
                self.check_login(page)
            except ValueError as e:
                print(f"Login falhou: {e}")
                ctx.close()
                raise e

            print("login está feito")

            skip_first = True

            while not self._stop.is_set():

                if skip_first:
                    skip_first = False
                else:
                    page.wait_for_timeout(refresh_period)

                new_transactions_sample = self.parse_transactions(page)
                # print("Transações coletadas com sucesso")
                # print(new_transactions_sample)

                if cfg.last_transaction_id is None:
                    new_transactions = []
                    cfg.last_transaction_id = self.get_last_transaction_id(new_transactions_sample)
                    print("Não há id de transação anterior, coletando novas à partir de agora")
                    continue
                else:
                    new_transactions = self.detect_new_transactions(cfg.last_transaction_id, new_transactions_sample)

                if len(new_transactions) == 0:
                    print("Nenhuma nova transação detectada")
                    continue

                print(f"\n{len(new_transactions)} novas transações detectadas:")
                for day_data in new_transactions:
                    print(f"\nDia: {day_data['day_date']}, Saldo parcial: R${day_data['day_partial_balance']:.2f}")
                    for transaction in day_data['transactions']:
                        print(f"  - {transaction['description_primary']} {transaction['description_secondary']} "
                            f"R${transaction['amount']:.2f} {transaction['time']}")
                        
                try:
                    self.on_new_data(new_transactions)
                except Exception as e:
                    print(f"Error in on_new_data handler: {e}")

                cfg.last_transaction_id = self.get_last_transaction_id(new_transactions_sample)


                # print("hmmm")
                # pkg = {"dummy data": "example"}
                # try:
                #     self.on_new_data(pkg)
                # except Exception:
                #     pass  # don’t let handler exceptions kill the loop
                # time.sleep(self.interval)

            
            ctx.close()

        if HIDE_WINDOW:
            display.stop()

    def convert_relative_date(self, date_text):
        dt = dateparser.parse(date_text, languages=["pt"])
        if dt is None:
            raise ValueError("Date parsing failed.")
        return dt.strftime('%Y-%m-%d')

    def check_login(self, page):
        # Verifica se está logado ou não
        # if page.locator("text={\"message\":\"local_rate_limited\",\"status\":429}").is_visible():
        if page.locator("text={\"message\":\"local_rate_limited\",\"status\":429}").count() > 0:
            raise ValueError("Error, too many requests")
        elif page.locator("text=Iniciar sessão").count() > 0:
            raise ValueError("Login necessário, rode o script de login")

        elif not page.locator("text=Sua última atividade").count() > 0:
            print("estado de login não identificado, talvez a pagina tenha mudado")
            raise ValueError("Estado de login não identificado, talvez a página tenha mudado")


    def parse_transactions(self, page):
        page.goto("https://www.mercadopago.com.br/banking/balance/movements")
        page.wait_for_load_state("load")
        # print("acessou transações")

        # text = page.locator(".binnacle-list").text_content()
        # print(text)
        days_el = page.locator(".binnacle-list .binnacle-rows-wrapper")
        days_data = []
        # print(f"Encontradas {days_el.count()} transações")
        if days_el.count() == 0:
            raise Exception("Nenhuma transação encontrada, talvez a página tenha mudado")

        for i in range(days_el.count()):
            day_el = days_el.nth(i)

            day_text = day_el.locator(".binnacle-rows-wrapper__header .binnacle-rows-wrapper__title").text_content()
            day_partial_balance_text = day_el.locator(".binnacle-rows-wrapper__header .binnacle-rows-wrapper__partial-balance .andes-money-amount").text_content()

            try:
                day_partial_balance = helper_functions.convert_brl_format(day_partial_balance_text)
            except ValueError as e:
                print(f"Saldo ta no formato errado")
                raise Exception("Erro ao parsear dados (day_partial_balance), talvez a página tenha mudado")

            try:
                day_date = self.convert_relative_date(day_text)
            except ValueError as e:
                print(f"Data ta no formato errado")
                raise Exception("Erro ao parsear dados (day_date), talvez a página tenha mudado")

            # print(f"Dia {day_date}: R${day_partial_balance:.2f}")
            day_data = {
                "day_date": day_date,
                "day_partial_balance": day_partial_balance,
                "transactions": []
            }

            rows_el = day_el.locator(".binnacle-row")
            for j in range(rows_el.count()):
                row_el = rows_el.nth(j)
                description_primary = row_el.locator(".andes-list__item-first-column .andes-list__item-primary .binnacle-row__title").text_content()

                sec_locator = row_el.locator(".andes-list__item-first-column .andes-list__item-secondary")
                description_secondary = sec_locator.text_content() if sec_locator.count() != 0 else ""

                amount = row_el.locator(".andes-list__item-second-column .andes-money-amount").text_content()
                time = row_el.locator(".andes-list__item-second-column .binnacle-row__time").text_content().strip()

                amount = helper_functions.convert_brl_format(amount)
                time = ":".join(time.split("h"))


                # print(f"Transacao {j+1}: {description_primary} - {description_secondary} - {amount} - {time}")

                day_data["transactions"].insert(0, {
                    "description_primary": description_primary,
                    "description_secondary": description_secondary,
                    "amount": amount,
                    "time": time
                })


            days_data.insert(0, day_data)

        # print("Transações coletadas com sucesso")
        # print(str(days_data))
        return days_data


    def get_last_transaction_id(self, transaction_sample):
        try:
            return f"{transaction_sample[-1]['day_date']}:{len(transaction_sample[-1]['transactions'])}"
        except IndexError:
            raise ValueError("Transaction sample is empty or malformed")


    def detect_new_transactions(self, last_transaction_id, transaction_sample):

        r = r"(\d{4}-\d{2}-\d{2}):(\d+)"
        match = re.match(r, last_transaction_id)
        if not match:
            raise ValueError("Invalid last transaction ID format")

        last_date = match.group(1)
        last_num = int(match.group(2))

        # print(f"Last transaction ID: {last_date}:{last_num}")

        new_transactions = []

        # print("\ndays:\n")
        for day_data in transaction_sample:
            if day_data['day_date'] < last_date:
                continue

            if day_data['day_date'] == last_date:
                if len(day_data['transactions']) > last_num:
                    # print(f"day {day_data['day_date']} have new transactions")

                    new_transactions = [{
                        'day_date': day_data['day_date'],
                        'day_partial_balance': day_data['day_partial_balance'],
                        'transactions': day_data['transactions'][last_num:],
                    }]

            if day_data['day_date'] > last_date:
                new_transactions.append(day_data.copy())
            # else:
            #     new_transactions.extend(day_data['transactions'])

        return new_transactions