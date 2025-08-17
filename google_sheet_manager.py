import gspread
from oauth2client.service_account import ServiceAccountCredentials
import encode_name
from datetime import datetime

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",      # read/write Sheets
    "https://www.googleapis.com/auth/drive.file",        # create new files
]

class GoogleSheetManager:
    def __init__(self, spreadsheet_id, credentials_file, logc):
        self.creds = ServiceAccountCredentials.from_json_keyfile_name(credentials_file, SCOPES)
        self.gc = gspread.authorize(self.creds)
        self.logc = logc

        self.spreadsheet_id = spreadsheet_id
        self.sh = self.gc.open_by_key(spreadsheet_id)
        self.ws_config = self.sh.worksheet("Configurações")
        self.ws_deposit = self.sh.worksheet("Inserir Depósito")
        self.ws_tracking = self.sh.worksheet("Acompanhamento")
        self.get_payment_names()
        self.get_categories()

    def get_payment_names(self):
        nicknames = self.ws_config.col_values(1)[1:]
        payment_names_list = self.ws_config.get(f"B2:B{len(nicknames)+1}")

        self.payment_names_to_nicknames = {}
        for i in range(len(nicknames)):
            if len(payment_names_list[i]) == 0 or len(nicknames[i]) == 0:
                continue

            names = payment_names_list[i][0].split(",")
            for name in names:
                self.payment_names_to_nicknames[encode_name.encode_name(name)] = nicknames[i]

    def get_config_column(self, column_name):
        column_names = self.ws_config.row_values(1)
        if column_name not in column_names:
            raise ValueError(f"Column '{column_name}' not found in configuration.")

        column_index = column_names.index(column_name) + 1
        return self.ws_config.col_values(column_index)[1:]
    
    def get_categories(self):
        self.categories = self.get_config_column("Categorias")

    def get_deposits(self):
        return self.ws_deposit.get_all_records()

    def insert_deposit(self, nickname, date, amount):
        self.ws_deposit.append_row([nickname, date, amount, 'Depósito na conta da casa', 'bot Ok', 'Depósito'], value_input_option="USER_ENTERED")
        self.logc(f'insert_deposit {nickname} {date} {amount}')
    
    def confirm_deposit(self, row_number):
        new_values = ['Depósito na conta da casa', 'bot Ok', 'Depósito']
        self.ws_deposit.update(f"D{row_number}:F{row_number}", [new_values], value_input_option="USER_ENTERED")
        self.logc(f'confirm_deposit {row_number}')

    def get_trackings(self):
        # return self.ws_tracking.get_all_records(expected_headers=['Data', 'Valor', 'Descrição', 'Categoria', 'Fonte (de onde veio esse dado)', 'Controle'])
        return self.ws_tracking.get("A:F")
    
    def update_earning(self, row_number, amount):
        new_values = [amount]
        self.logc(f'update_earning {row_number} {amount}')
        return self.ws_tracking.update(f"B{row_number}:B{row_number}", [new_values], value_input_option="USER_ENTERED")
    
    def add_erarning(self, date, amount, description):
        self.ws_tracking.append_row([date, amount, description, 'Rendimento', 'bot'], value_input_option="USER_ENTERED")
        self.logc(f'add_erarning {date} {amount} {description}')
    
    def insert_tracking(self, date, amount, description, category):
        self.ws_tracking.append_row([date, amount, description, category], value_input_option="USER_ENTERED")
        self.logc(f'insert_tracking {date} {amount} {description} {category}')

    def update_tracking(self, row_number, category, description):
        new_values = [description, category]
        self.logc(f'update_tracking {row_number} {category} {description}')
        return self.ws_tracking.update(f"C{row_number}:D{row_number}", [new_values], value_input_option="USER_ENTERED")

    # def handle_new_transactions(self, new_transactions):

    #     all_deposits = self.ws_deposit.get_all_values()
    #     print(all_deposits)

    #     for transaction in new_transactions:
            
    #         # if transaction['description_primary'] == ''




# gs_man = GoogleSheetManager(SPREADSHEET_ID)
# gs_man.insert_deposit("Bytos", "01/08/2025", 100.0, "")
# gs_man.insert_tracking('01/08/2025', 100.0, "Test Description", "Test Category")
