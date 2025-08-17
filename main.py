import time, re
from datetime import datetime
from monitor import PageMonitor
from google_sheet_manager import GoogleSheetManager

from encode_name import encode_name
import helper_functions
from TelegramManager import TelegramManager

# SPREADSHEET_ID = "1AM29wtnBMGiSrxmCxaQ-DQIKUmWNENG-mUrIuYqBzWo"
SPREADSHEET_ID = "1_6SqiYR3QugImRQRMfupSmkUT7w-pgIXj3qiKLrV378"
CREDENTIALS_FILE = "data/google_sheet_key.json"
REFRESH_PERIOD = 3600 # 1h
# REFRESH_PERIOD = 60   # 1m

log_file = f"logs/log {str(datetime.now()).replace(':', '-')}.txt"
def logc(msg):
    arquivo = open(log_file, "a")
    arquivo.write(str(datetime.now())+' - '+str(msg)+'\n')
    print(str(datetime.now()), '-', msg)
    arquivo.close()

def main():

    logc("Starting google sheet...")
    gs_man = GoogleSheetManager(SPREADSHEET_ID, CREDENTIALS_FILE, logc)
    logc("Started")

    logc("Starting telegram bot")
    tm = TelegramManager(logc)
    tm.start()
    tm.set_category_options(gs_man.categories)
    logc("Started")

    monitor = PageMonitor(REFRESH_PERIOD)

    def flatten_transactions(new_transactions):
        transactions = []
        for day in new_transactions:
            for transaction in day['transactions']:
                # print(f"{day['day_date']} {transaction['time']} R${transaction['amount']:.2f} {transaction['description_primary']}")
                transactions.append({
                    'date': day['day_date'],
                    'time': transaction['time'],
                    'amount': transaction['amount'],
                    'description_primary': transaction['description_primary'],
                    'description_secondary': transaction['description_secondary']
                })
        return transactions
    
    def get_organized_deposits(gs_man):
        raw_deposits = gs_man.get_deposits()

        # print('raw_deposits:', raw_deposits)

        organized_deposits = {}
        row_number = 1
        for deposit in raw_deposits:
            row_number += 1
            # print('deposit', deposit)
            nickname = deposit['Quem?']
            date = deposit['Data'].strip()
            try:
                amount = helper_functions.convert_brl_format(deposit['Valor'])
            except ValueError:
                amount = ''
            description = deposit['O que pagou?']
            status = deposit['Status']
            category = deposit['Categoria']

            try:
                date = helper_functions.convert_dmy_to_iso(date)
            except ValueError:
                pass

            if nickname not in organized_deposits:
                organized_deposits[nickname] = {}

            if date not in organized_deposits[nickname]:
                organized_deposits[nickname][date] = []
            
            organized_deposits[nickname][date].append({
                'amount': amount,
                'description': description,
                'status': status,
                'category': category,
                'row': row_number,
            })

        # print('organized_deposits:', organized_deposits)
        return organized_deposits
    
    def handle_processed_deposits(processed_deposit):
        # this function check for each new deposit, if its already on the sheet or if need to be inserted

        current_deposits = get_organized_deposits(gs_man)

        for deposit in processed_deposit:
            nickname = deposit['nickname']
            date = deposit['date']
            amount = deposit['amount']

            # print('current', current_deposits[nickname])
            # print('date', date)

            # print(f'\n\nchecking deposit {nickname} {date} R${amount:.2f}')
            logc(f'checking deposit {nickname} {date} R${amount:.2f}')

            found = False
            flag1 = False # this flag will be set if found in the sheet an deposit with the same amount, but the status in already filled or the description is not what is expected

            if nickname in current_deposits and date in current_deposits[nickname]:
                for current_deposit in current_deposits[nickname][date]:
                    if current_deposit['amount'] == amount:
                        # print('amount is equal')

                        if current_deposit['status'] == 'bot OK':
                            continue # was aded by the bot, so could not be this one

                        if(
                            current_deposit['status'] == '' and
                            (
                                current_deposit['description'] == 'Depósito na conta da casa'
                                or 
                                current_deposit['description'] == ''
                            )
                        ):
                            # print('should be this one', current_deposit)
                            current_deposit['description'] = 'Depósito na conta da casa'
                            current_deposit['status'] = 'bot Ok'
                            current_deposit['category'] = 'Depósito'
                            gs_man.confirm_deposit(current_deposit['row'])
                            logc(f'confirm line {current_deposit["row"]}')
                            found = True
                            break
                        else:
                            print('but status is filled or description is wrong, continue searching')
                            logc('but status is filled or description is wrong, continue searching')
                            flag1 = True
                if found: continue

            if flag1:
                # TODO: alert this to the user:
                print('ALERT! new deposit on bank was on sheet, with \'status\' field filled')
                logc('ALERT! new deposit on bank was on sheet, with \'status\' field filled')

            print(f'insert deposit')
            logc(f'inserting deposit {nickname} {date} {amount}')
            gs_man.insert_deposit(nickname, date, amount)

    def get_trackings():
        trackings = gs_man.get_trackings()[1:]

        for i, tracking in enumerate(trackings):
            try:
                date = tracking[0]
            except IndexError:
                date = ''

            try:
                amount = tracking[1]
            except IndexError:
                amount = ''

            try:
                description = tracking[2]
            except IndexError:
                description = ''

            try:
                category = tracking[3]
            except IndexError:
                category = ''

            try:
                source = tracking[4]
            except IndexError:
                source = ''

            try:
                control = tracking[5]
            except IndexError:
                control = ''


            if amount.strip() == '':
                amount = 0.0
            else:
                try:
                    amount = helper_functions.convert_brl_format(amount)
                except ValueError:
                    amount = None

            try:
                date = helper_functions.convert_dmy_to_iso(date)
            except ValueError:
                pass

            trackings[i] = {
                'date': date,
                'amount': amount,
                'description': description,
                'category': category,
                'source': source,
                'control': control,
                'row': i+2
            }

        return trackings
    
    def handle_processed_earnings(processed_earnings):
        trackings = get_trackings()

        def get_month_as_str(date_str):
            return datetime.strptime(date_str, '%Y-%m-%d').strftime("%m/%Y")

        packed_earnings = {}
        for earning in processed_earnings:
            mstr = get_month_as_str(earning['date'])
            if mstr not in packed_earnings:
                packed_earnings[mstr] = 0.0

            packed_earnings[mstr] += earning['amount']

        print('packed_earnings', packed_earnings)

        for mstr, amount in packed_earnings.items():
            month_str = "Rendimentos " + mstr
            month_str_enc = encode_name(month_str)
            for tracking in trackings:
                description = tracking['description']
                category = tracking['category']

                if encode_name(description) == month_str_enc:
                    if category == 'Rendimento':
                        gs_man.update_earning(tracking['row'], amount+tracking['amount'])
                        logc(f"updating tracking {tracking['row']} {amount+tracking['amount']}")
                        break
            else:
                gs_man.add_erarning('01/'+mstr, amount, month_str)
                logc(f"add earning {'01/'+mstr} {amount} {month_str}")

    


    def handle_processed_trackings(processed_trackings):
        
        current_trackings = get_trackings()

        existing_check_ids = []

        def new_id():
            check_id = helper_functions.generate_check_id(existing_check_ids)
            existing_check_ids.append(check_id)
            return check_id

        for current_tracking in current_trackings:
            number = helper_functions.extract_check_id(current_tracking['description'])

            if number is not None:
                existing_check_ids.append(number)

        # print("current check ids:", existing_check_ids)

        for tracking in processed_trackings:
            print(tracking)

            date = tracking['date']
            amount = tracking['amount']
            description = tracking['description']
            category = tracking['category']
            special_modes = tracking['special_modes']
            check = tracking['check']

            if description is None or category is None:
                check = True

            if description is None:
                description = 'Descrição pendente'

            
            if check:
                check_id = new_id()
                tm.send_category_msg(description, amount, check_id)
                logc(f"sending cat message {date} {amount} {description} {category}")
                description += f' check#{check_id}'

            gs_man.insert_tracking(date, amount, description, category)
            logc(f"inserting tracking {date} {amount} {description} {category}")


    def on_finished_categorize(check_id, category, description):
        print(f"received categorized:\nid: {check_id}\ncat: {category}\ndesc: {description}")
        logc(f"on_finished_categorize {check_id} {category} {description}")

        current_trackings = get_trackings()
        
        for tracking in current_trackings:
            curr_id = helper_functions.extract_check_id(tracking['description'])
            if curr_id is not None and curr_id == check_id:
                gs_man.update_tracking(tracking['row'], category, description)
                logc(f"updating tracking {tracking['row']} {category} {description}")
                break
        else:
            print(f"did not found tracking with check id {check_id}")
            logc(f"did not found tracking with check id {check_id}")

            

    def on_new_data(new_transactions):
        print('inserting new transactions into Google Sheets')
        transactions = flatten_transactions(new_transactions)

        # split trasaction types

        insert_as_deposit = []
        processed_earnings = []
        insert_as_tracking = []

        for transaction in transactions:
            if transaction['description_primary'] == 'Transferência Pix recebida' or transaction['description_primary'] == 'Transferência recebida':
                insert_as_deposit.append(transaction)
            elif transaction['description_primary'] == 'Rendimentos':
                processed_earnings.append({
                    'date': transaction['date'],
                    'amount': transaction['amount']
                })
            else:
                insert_as_tracking.append(transaction)

        # proccess deposits
        gs_man.get_payment_names()
        names_to_nicknames = gs_man.payment_names_to_nicknames
        processed_deposits = []
        for transaction in insert_as_deposit:
            name = encode_name(transaction['description_secondary'])
            if name not in names_to_nicknames:
                insert_as_tracking.append(transaction)
                continue
            processed_deposits.append({
                'nickname': names_to_nicknames[name],
                'date': transaction['date'],
                'amount': transaction['amount']
            })
        
        # proccess trackings
        processed_trackings = []
        for transaction in insert_as_tracking:

            desc1 = transaction['description_primary']
            desc2 = transaction['description_secondary']

            description = None
            category = None
            check = False
            special_modes = []

            desc2_enc = encode_name(desc2)

            if desc1 == 'Dinheiro reservado':
                if desc2_enc == '13 oseias':
                    description = 'Reservado para 13° Oséias'
                    category = 'Oséas'
                else:
                    description = f"Reservado em '{desc2}'"
                    category = 'Caixinha'
            elif desc1 == 'Dinheiro retirado':
                if desc2_enc == '13 oseias':
                    description = 'Retidado para 13° Oséias'
                    category = 'Oséas'
                else:
                    description = f"Retirado de '{desc2}'"
                    category = 'Caixinha'
            elif desc1 == 'Transferência enviada':
                if desc2_enc == 'tenda atacado sa':
                    description = 'Compra tenda'
                    category = 'Mercado geral'
                    special_modes.append('tenda')
            elif desc1 == 'Transferência Pix enviada':
                if desc2_enc == 'oseas dias da silva selvagio':
                    description = 'Salário Oséas'
                    category = 'Oséas'
                elif desc2_enc == 'walterdisney lima santos':
                    description = 'Pagamento vigia'
                    category = 'Vigia'
            elif desc1 == 'Pagamento com QR Pix':
                if desc2_enc == 'tenda atacado sa':
                    description = 'Compra tenda'
                    category = 'Mercado geral'
                    special_modes.append('tenda')
                elif desc2_enc == 'companhia paulista de forca e luz':
                    description = 'Pagamento conta de luz'
                    category = 'Luz'
                elif desc2_enc == 'telefonica brasil s a':
                    description = 'Pagamento conta de internet'
                    category = 'Internet'
                elif desc2_enc == 'supermercados jau serve ltda':
                    description = 'o que foi comprado no jau?'
                    check = True
            elif desc1 == 'Pagamento':
                if desc2_enc == 'varejao passarinh':
                    description = 'compra no passarinho'
                    category = 'Mercado geral'
                    check = True
                elif desc2_enc == 'jau serve lj 32':
                    description = 'o que foi comprado no jau?'
                    check = True
            elif desc1 == 'Reserva programada':
                if desc2_enc == '13 oseias':
                    description = 'Reservado para 13° Oséias'
                    category = 'Oséas'
            elif desc1 == 'Pagamento de contas':
                if desc2_enc == 'saae sao carlos sp':
                    description = 'Pagamento conta de água'
                    category = 'Água'
                elif desc2_enc == 'rfb - doc arrec emp':
                    description = 'Imposrto oséias'
                    category = 'Oséas'
                elif desc2_enc == 'vivo movel sp':
                    description = 'Pagamento conta de internet'
                    category = 'Internet'
                elif desc2_enc == 'cpfl paulista':
                    description = 'Pagamento conta de luz'
                    category = 'Luz'
            
            if description is None:
                if desc1 == 'Transferência enviada' or desc1 == 'Transferência Pix enviada':
                    if desc2 in names_to_nicknames and transaction['amount'] >= 3000:
                        description = 'Para sacar aluguel'
                        category = 'Aluguel marcos'
                        check = True

            if description is None:
                description = f'{desc1}: {desc2}'

            if category is None:
                check = True
                    
            processed_trackings.append({
                'date': transaction['date'],
                'amount': transaction['amount'],
                'description': description,
                'category': category,
                'special_modes': special_modes,
                'check': check,
            })

        print('processed_deposit', processed_deposits)
        print('processed_trackings', processed_trackings)
        print('processed_earnings', processed_earnings)
        print('\n')
        
        handle_processed_deposits(processed_deposits)
        handle_processed_earnings(processed_earnings)
        handle_processed_trackings(processed_trackings)
            

            
    
    logc("Starting MP monitor")
    monitor.set_on_new_data(on_new_data)
    monitor.start()
    logc("Started")                
            

    tm.set_on_finished_categorize_function(on_finished_categorize)


    time.sleep(2)

    try:
        # 3) Your “main” work goes here
        while True:
            # e.g. a CLI, HTTP server, other tasks…
            time.sleep(1)
    except KeyboardInterrupt:
        logc("Stopping…")
    finally:
        # 4) Clean up
        monitor.stop()
        logc("Monitor stopped, exiting.")

if __name__ == "__main__":
    main()
