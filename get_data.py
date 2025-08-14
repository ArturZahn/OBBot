import pandas as pd
from pathlib import Path
from playwright.sync_api import sync_playwright
import re, dateparser, json
from pyvirtualdisplay import Display

from configs import ConfigManager

CONFIG_FILE_PATH = "data/mp_scraper_config.json"

DEFAUTL_CONFIG = {
    "last_transaction_id": None
}

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
    """
    Convert strings such as R$+10,00 R$-10,00 +R$10,00 -R$10,00
    to a float (positive or negative).  Raises ValueError on unknown format.
    """
    m = BRL_PATTERN.match(text)
    if not m:
        raise ValueError("Balance format not recognized.")

    # Decide which sign applies (cannot have both)
    prefix, post = m["prefix_sign"], m["post_sign"]
    if prefix and post:
        raise ValueError("Conflicting signs in balance string.")

    sign = -1 if (prefix == "-" or post == "-") else 1

    integer_part = m["int"].replace(".", "")
    cents_part = m["dec"]
    return sign * float(f"{integer_part}.{cents_part}")

def convert_relative_date(date_text):
    dt = dateparser.parse(date_text, languages=["pt"])
    if dt is None:
        raise ValueError("Date parsing failed.")
    return dt.strftime('%Y-%m-%d')

def check_login(page):
    # Verifica se está logado ou não
    # if page.locator("text={\"message\":\"local_rate_limited\",\"status\":429}").is_visible():
    if page.locator("text={\"message\":\"local_rate_limited\",\"status\":429}").count() > 0:
        raise ValueError("Error, too many requests")
    elif page.locator("text=Iniciar sessão").count() > 0:
        raise ValueError("Login necessário, rode o script de login")

    elif not page.locator("text=Sua última atividade").count() > 0:
        print("estado de login não identificado, talvez a pagina tenha mudado")
        raise ValueError("Estado de login não identificado, talvez a página tenha mudado")


def parse_transactions(page, page_number=None):

    page.goto("https://www.mercadopago.com.br/banking/balance/movements" + (f"?page={page_number}" if page_number else ""))
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
            day_partial_balance = convert_brl_format(day_partial_balance_text)
        except ValueError as e:
            print(f"Saldo ta no formato errado")
            raise Exception("Erro ao parsear dados (day_partial_balance), talvez a página tenha mudado")

        try:
            day_date = convert_relative_date(day_text)
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

            amount = convert_brl_format(amount)
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


def get_last_transaction_id(transaction_sample):
    try:
        return f"{transaction_sample[-1]['day_date']}:{len(transaction_sample[-1]['transactions'])}"
    except IndexError:
        raise ValueError("Transaction sample is empty or malformed")


def detect_new_transactions(last_transaction_id, transaction_sample):

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

def main():

    USE_DISPLAY = False
    if USE_DISPLAY:
        display = Display(visible=0, size=(200, 100))
        display.start()

    cfg = ConfigManager(CONFIG_FILE_PATH, DEFAUTL_CONFIG)
    cfg.load()

    refresh_period = 10*1000
    refresh_period = 1

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
            check_login(page)
        except ValueError as e:
            print(f"Login falhou: {e}")
            ctx.close()
            raise e

        print("login está feito")

        cfg.last_transaction_id = '2022-01-01:1'

        skip_first = True

        page_number = 14

        while True:

            if skip_first:
                skip_first = False
            else:
                page.wait_for_timeout(refresh_period)

            new_transactions_sample = parse_transactions(page, page_number)
            page_number -= 1
            if page_number <= 0:
                break
            # print("Transações coletadas com sucesso")
            # print(new_transactions_sample)

            # if cfg.last_transaction_id is None:
            #     new_transactions = []
            #     cfg.last_transaction_id = get_last_transaction_id(new_transactions_sample)
            #     print("Não há id de transação anterior, coletando novas à partir de agora")
            #     continue
            # else:
            #     new_transactions = detect_new_transactions(cfg.last_transaction_id, new_transactions_sample)
            new_transactions = new_transactions_sample

            if len(new_transactions) == 0:
                print("Nenhuma nova transação detectada")
                continue

            print(f"\n{len(new_transactions)} novas transações detectadas:")
            print(new_transactions)
            # for day_data in new_transactions:
            #     print(f"\nDia: {day_data['day_date']}, Saldo parcial: R${day_data['day_partial_balance']:.2f}")
            #     for transaction in day_data['transactions']:
            #         print(f"  - {transaction['description_primary']} {transaction['description_secondary']} "
            #             f"R${transaction['amount']:.2f} {transaction['time']}")
                    
            cfg.last_transaction_id = get_last_transaction_id(new_transactions_sample)

        ctx.close()

    if USE_DISPLAY:
        display.stop()


if __name__ == "__main__":
    main()
