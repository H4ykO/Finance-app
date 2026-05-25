"""
Inicia o bot do Telegram.

Uso:
    python -m scripts.run_bot

Pré-requisitos (no .env):
    TELEGRAM_BOT_TOKEN=...        (do @BotFather)
    TELEGRAM_ALLOWED_USER_IDS=... (seu id, do @userinfobot)

O bot fica rodando até você apertar Ctrl+C. Enquanto roda, você pode
mandar mensagens para o seu bot no Telegram e elas viram lançamentos.

DICA: deixe este comando rodando num terminal separado, em paralelo
ao app (python main.py). Os dois compartilham o mesmo banco.
"""

from app.database.connection import init_database
from app.services.telegram_bot import FinanceBot


def main() -> None:
    # Garante que o banco existe (idempotente)
    init_database()

    try:
        bot = FinanceBot()
    except RuntimeError as e:
        print(f"ERRO: {e}")
        return

    bot.run()


if __name__ == "__main__":
    main()
