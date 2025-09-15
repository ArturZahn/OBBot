import pandas as pd
from pathlib import Path
from playwright.sync_api import sync_playwright

def fazer_login():
    print("Fazendo login...")
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir="mp_profile",      # <-- change folder if you like
            headless=False
        )
        page = ctx.new_page()
        page.goto("https://www.mercadopago.com.br/home")
        page.wait_for_selector("text=Últimas atividades", timeout=5*60*1000)
        print("Login feito com sucesso")
        ctx.close()

fazer_login()