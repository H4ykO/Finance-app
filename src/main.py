"""
Ponto de entrada do Finance App.

Rodando no Mac:
    python main.py

ft.app(target=main) inicia o Flet:
  - Cria uma instância de `Page` (janela do app)
  - Chama nossa função `main(page)` passando essa page
  - A função monta a UI e atualiza a tela conforme necessário
"""

import flet as ft

from app.config import settings
from app.database.connection import init_database
from app.services.telegram_bot import start_in_background
from app.ui.app import FinanceApp


def main(page: ft.Page) -> None:
    """Função chamada pelo Flet quando a janela é criada."""
    # Mostra onde os dados estão sendo salvos (útil para depurar,
    # especialmente no app empacotado, onde o banco fica em
    # ~/Library/Application Support/FinanceApp/).
    print(f"[FinanceApp] Dados em: {settings.DATA_DIR}")

    # Garante que o banco e tabelas existem.
    # Idempotente — não apaga nem altera dados existentes.
    init_database()

    # Inicia o bot do Telegram em segundo plano, junto com o app.
    # Se o token não estiver configurado, segue sem o bot (não quebra).
    # A thread é daemon: o bot desliga sozinho quando você fecha o app.
    start_in_background()

    # Inicia o controller, que vai mostrar a tela de login
    app = FinanceApp(page)
    app.start()


# ft.app(main) é chamado no nível do módulo (não dentro de
# `if __name__ == "__main__"`) porque o `flet build` espera encontrar
# esta chamada para descobrir o ponto de entrada do app empacotado.
# Funciona tanto rodando `python main.py` quanto no .app gerado.
ft.app(target=main)
