"""
Bot do Telegram para registrar lançamentos por mensagem.

ARQUITETURA (importante para testabilidade):
Separamos em duas camadas:
  1. LÓGICA (funções `handle_*`): recebem texto + user_id, retornam
     texto de resposta. NÃO dependem da rede nem da lib do Telegram.
     São 100% testáveis offline.
  2. REDE (classe `FinanceBot`): conecta na API do Telegram e liga
     cada mensagem recebida à função de lógica correspondente.

Assim conseguimos testar todo o comportamento sem precisar de token
nem internet — só a camada fina de rede fica sem teste automatizado.

SEGURANÇA:
O bot só responde a IDs de usuário autorizados (TELEGRAM_ALLOWED_USER_IDS
no .env). Qualquer outra pessoa que achar o bot recebe uma recusa.
Isso é essencial: sem isso, qualquer um poderia registrar transações
no seu banco de dados.
"""

from datetime import date
from decimal import Decimal
from typing import Optional

from app.config import settings
from app.database.connection import get_session
from app.database.models import User
from app.services import transaction_service as tx_service
from app.services.message_parser import ParseError, parse_message
from app.ui.theme import format_brl  # reusa formatação BR


# ---------------------------------------------------------------------------
# Autorização
# ---------------------------------------------------------------------------
def get_allowed_user_ids() -> set[int]:
    """Lê os IDs autorizados do .env e retorna como set de inteiros."""
    raw = settings.TELEGRAM_ALLOWED_USER_IDS.strip()
    if not raw:
        return set()
    ids = set()
    for part in raw.split(","):
        part = part.strip()
        if part.isdigit():
            ids.add(int(part))
    return ids


def is_authorized(telegram_user_id: int) -> bool:
    """True se o usuário do Telegram pode usar o bot."""
    allowed = get_allowed_user_ids()
    # Se nenhum ID configurado, negamos tudo (fail-safe seguro)
    return telegram_user_id in allowed if allowed else False


# ---------------------------------------------------------------------------
# Helper: descobrir qual usuário do app usar
# ---------------------------------------------------------------------------
def _get_app_user_id() -> Optional[int]:
    """
    Retorna o id do usuário do app (o admin) que receberá os lançamentos.

    Para uso pessoal, mapeamos todos os lançamentos do bot para o admin.
    Em um cenário multiusuário, mapearíamos cada telegram_id a um user.
    """
    with get_session() as session:
        user = session.query(User).first()
        return user.id if user else None


# ---------------------------------------------------------------------------
# LÓGICA DOS COMANDOS (testável, sem rede)
# ---------------------------------------------------------------------------
def handle_start() -> str:
    """Resposta ao /start — mensagem de boas-vindas com instruções."""
    return (
        "👋 Hi! I'm your finance assistant.\n\n"
        "To record, send something like:\n"
        "• <code>45,90 uber</code>\n"
        "• <code>120 conta de luz amanhã</code>\n"
        "• <code>+3000 salário</code>\n"
        "• <code>recebi 500 freela ontem</code>\n\n"
        "Commands:\n"
        "/balance — month summary\n"
        "/recent — last entries\n"
        "/undo — delete the last entry\n"
        "/help — this message"
    )


def handle_register(text: str, telegram_user_id: int, today: Optional[date] = None) -> str:
    """
    Processa uma mensagem de lançamento e grava no banco.

    Retorna o texto de confirmação (ou erro) para enviar de volta.
    """
    if not is_authorized(telegram_user_id):
        return "⛔ You are not authorized to use this bot."

    app_user_id = _get_app_user_id()
    if app_user_id is None:
        return "⚠️ No user configured in the app. Run init_db first."

    # Carrega as regras de categorização do usuário para passar ao parser.
    # Sem isso, o bot ignoraria as regras editáveis de categorização.
    from app.services.category_service import get_user_rules_map
    with get_session() as session:
        user_rules = get_user_rules_map(session, app_user_id)

    try:
        parsed = parse_message(text, today=today, user_rules=user_rules)
    except ParseError as e:
        return (
            f"❓ I didn't understand: {e}\n\n"
            "Try something like <code>45.90 uber</code> or send /help."
        )

    # Resolve a categoria (nome -> id)
    category_id = None
    if parsed.category_name:
        from app.database.models import Category
        with get_session() as session:
            from sqlalchemy import select
            cat = session.scalar(select(Category).where(Category.name == parsed.category_name))
            category_id = cat.id if cat else None

    with get_session() as session:
        tx_service.create_transaction(
            session=session,
            user_id=app_user_id,
            description=parsed.description,
            amount=parsed.amount,
            kind=parsed.kind,
            occurred_at=parsed.occurred_at,
            category_id=category_id,
        )

    # Monta confirmação
    tipo_label = "Expense recorded" if parsed.kind == "expense" else "Income recorded"
    cat_label = f" ({parsed.category_name})" if parsed.category_name else ""
    sinal = "" if parsed.kind == "expense" else "+"
    data_label = parsed.occurred_at.strftime("%d/%m/%Y")

    return (
        f"✓ {tipo_label}:\n"
        f"<b>{sinal}{format_brl(parsed.amount)}</b> — {parsed.description}{cat_label}\n"
        f"📅 {data_label}\n\n"
        f"<i>To undo, send /undo</i>"
    )


def handle_balance(telegram_user_id: int, today: Optional[date] = None) -> str:
    """Resumo do mês: total de gastos, entradas e saldo."""
    if not is_authorized(telegram_user_id):
        return "⛔ You are not authorized to use this bot."

    if today is None:
        today = date.today()

    app_user_id = _get_app_user_id()
    if app_user_id is None:
        return "⚠️ No user configured."

    from app.services import billing_cycle
    first, last = billing_cycle.month_bounds(today)

    with get_session() as session:
        expenses = tx_service.search_transactions(
            session, app_user_id, kind="expense", start=first, end=last
        )
        incomes = tx_service.search_transactions(
            session, app_user_id, kind="income", start=first, end=last
        )

    total_exp = sum((t.amount for t in expenses), Decimal("0"))
    total_inc = sum((t.amount for t in incomes), Decimal("0"))
    saldo = total_inc - total_exp

    mes_label = today.strftime("%m/%Y")
    return (
        f"📊 Summary for {mes_label}:\n\n"
        f"Income: <b>{format_brl(total_inc)}</b>\n"
        f"Expenses: <b>{format_brl(total_exp)}</b>\n"
        f"Balance: <b>{format_brl(saldo)}</b>\n\n"
        f"({len(expenses)} expenses, {len(incomes)} income)"
    )


def handle_recent(telegram_user_id: int, limit: int = 5) -> str:
    """Lista os últimos lançamentos."""
    if not is_authorized(telegram_user_id):
        return "⛔ You are not authorized to use this bot."

    app_user_id = _get_app_user_id()
    if app_user_id is None:
        return "⚠️ No user configured."

    with get_session() as session:
        txs = tx_service.list_recent_transactions(session, app_user_id, limit=limit)
        rows = [
            (t.occurred_at, t.description, t.amount, t.kind)
            for t in txs
        ]

    if not rows:
        return "No entries yet."

    lines = ["🧾 Last entries:\n"]
    for occurred_at, desc, amount, kind in rows:
        sinal = "−" if kind == "expense" else "+"
        lines.append(f"{occurred_at.strftime('%d/%m')} {sinal}{format_brl(amount)} — {desc}")
    return "\n".join(lines)


def handle_undo(telegram_user_id: int) -> str:
    """Apaga o último lançamento registrado (correção de erro de digitação)."""
    if not is_authorized(telegram_user_id):
        return "⛔ You are not authorized to use this bot."

    app_user_id = _get_app_user_id()
    if app_user_id is None:
        return "⚠️ No user configured."

    with get_session() as session:
        txs = tx_service.list_recent_transactions(session, app_user_id, limit=1)
        if not txs:
            return "No entries to undo."
        last = txs[0]
        desc = last.description
        amount = last.amount
        tx_service.delete_transaction(session, last.id, app_user_id)

    return f"🗑️ Removed: {format_brl(amount)} — {desc}"


# ---------------------------------------------------------------------------
# CAMADA DE REDE (só roda no Mac, com token e internet)
# ---------------------------------------------------------------------------
class FinanceBot:
    """
    Liga a lógica acima à API do Telegram.

    Esta classe só é instanciada quando rodamos o bot de verdade
    (scripts/run_bot.py). A lib python-telegram-bot é importada DENTRO
    do __init__ para que o resto do app (e os testes) não precise
    dela instalada só para importar este módulo.
    """

    def __init__(self):
        token = settings.TELEGRAM_BOT_TOKEN.strip()
        if not token:
            raise RuntimeError(
                "TELEGRAM_BOT_TOKEN não configurado no .env. "
                "Crie um bot com o @BotFather e cole o token lá."
            )
        if not get_allowed_user_ids():
            raise RuntimeError(
                "TELEGRAM_ALLOWED_USER_IDS não configurado no .env. "
                "Descubra seu ID com o @userinfobot e coloque no .env "
                "(por segurança, o bot não funciona sem isso)."
            )
        self.token = token

    def run(self) -> None:
        """Inicia o bot (bloqueante — fica escutando mensagens)."""
        # Import local: só precisa da lib quando realmente rodamos o bot
        from telegram import Update
        from telegram.ext import (
            Application,
            CommandHandler,
            MessageHandler,
            filters,
        )

        app = Application.builder().token(self.token).build()

        # --- Adaptadores: convertem o Update do Telegram em chamadas à lógica ---
        async def cmd_start(update: Update, context):
            await update.message.reply_html(handle_start())

        async def cmd_saldo(update: Update, context):
            uid = update.effective_user.id
            await update.message.reply_html(handle_balance(uid))

        async def cmd_ultimas(update: Update, context):
            uid = update.effective_user.id
            await update.message.reply_html(handle_recent(uid))

        async def cmd_desfazer(update: Update, context):
            uid = update.effective_user.id
            await update.message.reply_html(handle_undo(uid))

        async def cmd_ajuda(update: Update, context):
            await update.message.reply_html(handle_start())

        async def on_message(update: Update, context):
            uid = update.effective_user.id
            text = update.message.text or ""
            await update.message.reply_html(handle_register(text, uid))

        app.add_handler(CommandHandler("start", cmd_start))
        app.add_handler(CommandHandler("help", cmd_ajuda))
        app.add_handler(CommandHandler("balance", cmd_saldo))
        app.add_handler(CommandHandler("recent", cmd_ultimas))
        app.add_handler(CommandHandler("undo", cmd_desfazer))
        # Qualquer texto que não seja comando = tentativa de registro
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))

        # Quando rodando numa thread (dentro do app), não há event loop
        # nessa thread por padrão. Criamos um explicitamente — isso também
        # cobre o Python 3.14, que não cria loop implícito.
        import asyncio
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            asyncio.set_event_loop(asyncio.new_event_loop())

        print("Telegram bot running.")
        # drop_pending_updates=False é ESSENCIAL para o seu caso de uso:
        # quando você abre o app, o bot busca TODAS as mensagens que
        # chegaram enquanto o app esteve fechado e as processa. Se fosse
        # True, ele descartaria o acúmulo. O Telegram retém pendentes ~24h.
        #
        # stop_signals=None: tratar sinais (Ctrl+C) só funciona na thread
        # principal. Como o bot pode rodar numa thread secundária (dentro
        # do app), desligamos o tratamento de sinais para não dar erro.
        app.run_polling(drop_pending_updates=False, stop_signals=None)


def start_in_background() -> bool:
    """
    Inicia o bot numa thread separada (daemon), para rodar junto com o app.

    Retorna True se o bot foi iniciado, False se não (ex: token não
    configurado). NUNCA lança exceção — o bot é um extra e não pode
    derrubar o app. Se algo der errado, o app segue normalmente sem o bot.

    A thread é daemon: morre automaticamente quando o app fecha, então
    o bot "liga ao abrir o app, desliga ao fechar" sem código extra.
    """
    import threading

    try:
        bot = FinanceBot()  # valida token e IDs no __init__
    except RuntimeError as e:
        # Token/IDs não configurados — segue sem bot, sem quebrar o app
        print(f"[bot] Não iniciado: {e}")
        return False

    def _runner():
        try:
            bot.run()
        except Exception as e:  # noqa: BLE001
            # Qualquer falha do bot fica contida na thread, não afeta o app
            print(f"[bot] Encerrado com erro: {e}")

    thread = threading.Thread(target=_runner, daemon=True, name="telegram-bot")
    thread.start()
    print("[bot] Iniciado em segundo plano (junto com o app).")
    return True
