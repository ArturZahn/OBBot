import time, re, asyncio, contextlib, secrets
from telegram.helpers import escape_markdown
from TelegramManagerCore import TelegramManagerCore
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ForceReply,
)
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    filters,
)


ASK_DESC, ASK_OPTION = range(2)

from configs import ConfigManager
CONFIG_FILE_PATH = 'data/telegram_manager_config.json'
DEFAUTL_CONFIG = {
    "token": None,
    "cat_msgs": {},
}
cfg = ConfigManager(CONFIG_FILE_PATH, DEFAUTL_CONFIG)
cfg.load()
token = cfg.token

# import logging
# logging.basicConfig(
#     level=logging.INFO,
#     format="%(asctime)s %(levelname)s [%(threadName)s] %(name)s: %(message)s",
# )

SET_CATEGORY_CHAT_PATTERN = re.compile(r"^/set_category_chat\s+(?P<password>.+)\s*$")

class TelegramManager(TelegramManagerCore):
    def __init__(self, logc):
        super().__init__(token)

        self.category_options = ['Categorias não foram carregadas']
        self.logc = logc

    def set_handlers(self):
        
        print('setting handlers')

        self._help_msg = (
            '/start - Inicia o bot\n'
            '/help - Mostra essa mensagem\n'
            '/set_category_chat <password> - Usa chat atual para definir categorias\n'
        )

        self._app.add_handler(CommandHandler('start', self._cmd_start))
        self._app.add_handler(CommandHandler('help', self._help_cmd))
        self._app.add_handler(CommandHandler('set_category_chat', self._set_category_chat_cmd))

        self.install_category_flow()

    # --- sample handlers ---
    async def _cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text('Bot up in another thread 🚀')

    async def _help_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(self._help_msg)

    async def _set_category_chat_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = update.message.text
        m = SET_CATEGORY_CHAT_PATTERN.match(text)
        if not m:
            await update.message.reply_text(
                '❌ *Comando inválido.*\n'
                'Use o formato:\n'
                '`/set_category_chat <senha>`',
                parse_mode='Markdown'
            )
            return
        
        if m['password'] != 'senha':
            await update.message.reply_text(f'Senha incorreta')
            return

        cfg.category_chat_id = update.effective_chat.id
        await update.message.reply_text(f'Ok! ✅\nAgora esse chat será usado para definir as categorias de gastos')

    async def send_category_msg_async(self, description, amount, check_id):
        try:
            chat_id = cfg.category_chat_id
        except AttributeError:
            print('chat still not defined')
            return
        
        finally:
            # await self._app.bot.send_message(chat_id=chat_id, text=msg)
            print("Enviando...")
            await self.send_category_entry_button(chat_id, description, amount, check_id)
    
    def send_category_msg(self, description, amount, check_id):

        return self.run_coroutine_threadsafe(
            self.send_category_msg_async(description, amount, check_id)
        )
    
    def set_category_options(self, options):
        if not isinstance(options, list):
            raise ValueError('Options must be a list')
        
        self.category_options = options
    

    ####################################### to handle messages to categorize trackings #######################################

    def install_category_flow(self):
        conv = ConversationHandler(
            entry_points=[
                # note: pattern now expects "START_FLOW:<token>"
                CallbackQueryHandler(self._cb_start_category_flow, pattern=r"^START_FLOW:")
            ],
            states={
                ASK_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND & filters.REPLY, self._on_description)],
                ASK_OPTION: [CallbackQueryHandler(self._on_option, pattern=r"^OPT:")],
            },
            fallbacks=[CommandHandler("cancel", self._cancel)],
            per_chat=True, per_user=True, name="category_flow",
        )
        self._app.add_handler(conv)

    async def send_category_entry_button(self, chat_id: int, original_description: str, amount: float, check_id: str):
        # 1) create a compact token and stash payload in app.bot_data
        # token = secrets.token_urlsafe(6)  # ~11 chars, safe for callback_data
        
        original_description = escape_markdown(original_description, version=2)

        print(f"sending cat msg {chat_id} {original_description} {amount:.2f} {check_id}")

        cfg.cat_msgs[check_id] = {
            "orig_desc": original_description,
            "amount": float(amount),
        }

        msg_text = (
            f"*Nova transação:*\n"
            f'Descrição: {original_description}\n'
            f"Valor: R$ {amount:.2f}\n"
        )

        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("Categorizar", callback_data=f"START_FLOW:{check_id}")
        ]])
        await self._app.bot.send_message(chat_id=chat_id, text=msg_text, reply_markup=kb, parse_mode="Markdown")

    # 1) Button clicked → fetch payload via token; ask for description with ForceReply
    async def _cb_start_category_flow(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        q = update.callback_query
        await q.answer()

        # token comes after "START_FLOW:"
        _, check_id = q.data.split(":", 1)

        try:
            payl = cfg.cat_msgs[check_id]
        except (KeyError, TypeError):
            with contextlib.suppress(Exception):
                await q.message.delete()
            await q.message.chat.send_message("Não encontrei os dados da transação. Tente novamente.")
            return ConversationHandler.END
        
        print("2:", payl)

        orig_desc = payl["orig_desc"]
        amount = payl["amount"]

        # keep in user_data for the rest of the flow
        ud = context.user_data
        ud["check_id"] = check_id

        # delete the button message
        with contextlib.suppress(Exception):
            await q.message.delete()

        # ask for description and force reply UI, including the original info
        prompt = await q.message.chat.send_message(
            f'Descrição: {orig_desc}\n'
            f"Valor: R$ {amount:.2f}\n"
            "Digite a *descrição* desse gasto respondendo esta mensagem:\n",
            parse_mode="Markdown",
            reply_markup=ForceReply(selective=True),
        )

        ud["prompt_id"] = prompt.message_id
        payl["prompt_id"] = prompt.message_id
        return ASK_DESC

    # 2) User replies → show options; include original info in options prompt; cleanup
    async def _on_description(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    
        check_id = context.user_data.get('check_id')
        if not check_id or check_id not in cfg.cat_msgs:
            return ConversationHandler.END
        payl = cfg.cat_msgs[check_id]
        prompt_id = payl['prompt_id']


        if not update.message.reply_to_message or update.message.reply_to_message.message_id != prompt_id:
            return ASK_DESC

        payl["desc"] = update.message.text.strip()
        orig_desc = payl['orig_desc']
        amount = payl['amount']
        prompt_id = payl['prompt_id']
        chat_id = update.effective_chat.id

        # delete the user's reply (optional/clean)
        with contextlib.suppress(Exception):
            await update.message.delete()

        # Instead of deleting the prompt, EDIT it to become the options message  ⬇️
        # inside _on_description, after you got desc and before sending options
        options = self.category_options
        kb = InlineKeyboardMarkup([[InlineKeyboardButton(opt, callback_data=f"OPT:{opt}")]
                                   for opt in options])

        # 1) send options *as a reply* to the ForceReply message
        msg = await context.bot.send_message(
            chat_id=chat_id,
            text=(
                f'Descrição: {orig_desc}\n'
                f"Valor: R$ {amount:.2f}\n"
                "Agora escolha uma categoria:\n"
            ),
            reply_markup=kb,
            reply_to_message_id=prompt_id,   # <-- key line
        )

        # 2) now delete the prompt (the “reply to …” banner goes away)
        with contextlib.suppress(Exception):
            await context.bot.delete_message(chat_id=chat_id, message_id=prompt_id)

        payl['options_msg_id'] = msg.message_id
        del payl['prompt_id']
        return ASK_OPTION

    # 3) User picks an option → delete options message; post final summary ONLY
    async def _on_option(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        q = update.callback_query
        await q.answer()
        check_id = context.user_data['check_id']
        payl = cfg.cat_msgs[check_id]
        option = q.data.split(":", 1)[1]
        desc = payl['desc']
        amount = payl['amount']

        # delete the options message
        with contextlib.suppress(Exception):
            await q.message.delete()

        # final message only (as you requested)
        await q.message.chat.send_message(f"Gasto categorizado ✅\nR${amount:.2f} - {option}\n{desc}\n")

        self._on_finished_categorize(check_id, option, desc)

        del cfg.cat_msgs[check_id]
        context.user_data.clear()
        return ConversationHandler.END

    async def _cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        check_id = context.user_data.get('check_id')

        # If check_id exists in cfg.cat_msgs, proceed to clean up
        if check_id in cfg.cat_msgs:
            payl = cfg.cat_msgs[check_id]

            # Clean up prompt message and options message if they exist
            prompt_id = payl.get('prompt_id')
            options_msg_id = payl.get('options_msg_id')

            # Delete prompt and options message if they exist
            with contextlib.suppress(Exception):
                if prompt_id:
                    await context.bot.delete_message(chat_id=chat_id, message_id=prompt_id)
                if options_msg_id:
                    await context.bot.delete_message(chat_id=chat_id, message_id=options_msg_id)

            # Clear the entry from cat_msgs after cleanup
            del cfg.cat_msgs[check_id]

        # Clear user_data for safety
        context.user_data.clear()

        # Inform the user that the process was cancelled
        await update.message.reply_text("Cancelado.")

        return ConversationHandler.END

    ##########################################################################################################################

    def set_on_finished_categorize_function(self, on_finished_categorize):
        self._on_finished_categorize = on_finished_categorize

        
        


def main():
    tm = TelegramManager()
    tm.start()
    tm.set_category_options([
        'Depósito',
        'Oséas',
        'Internet',
        'Piscina',
        'Gás',
        'Vigia',
        'Mercado mistura',
        'Mercado geral',
        'Água',
        'Luz',
        'Cachorro',
        'Manutenção',
        'Rendimento',
        'Outros',
        'Aluguel marcos',
        'Caixinha',
    ])

    time.sleep(5)
    tm.send_category_msg("something", 51)
    try:
        while True:
            time.sleep(5)


    except KeyboardInterrupt:
        print('\nCtrl+C on main. Stopping bot…')
        tm.stop()
        print('Bye!')


if __name__ == "__main__":
    main()
