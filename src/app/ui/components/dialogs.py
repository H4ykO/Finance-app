"""
Helpers de diálogos modais reutilizáveis.

Flet usa `page.open(dialog)` / `page.close(dialog)` para modais.
Centralizamos aqui a criação de dois diálogos comuns:
  - confirmação (sim/não), usada antes de remover algo
  - já o formulário de transação/bill fica nas próprias views, pois
    são específicos demais para generalizar bem.
"""

from typing import Callable

import flet as ft

from app.ui.theme import Colors, Font, Radius


def confirm_dialog(
    page: ft.Page,
    title: str,
    message: str,
    on_confirm: Callable[[], None],
    confirm_label: str = "Confirm",
    danger: bool = False,
) -> None:
    """
    Abre um diálogo de confirmação sim/não.

    `on_confirm` é chamado se o usuário confirmar. `danger=True` deixa
    o botão de confirmação vermelho (para ações destrutivas como remover).
    """

    def handle_confirm(e):
        page.close(dialog)
        on_confirm()

    def handle_cancel(e):
        page.close(dialog)

    confirm_btn = ft.TextButton(
        content=ft.Text(
            confirm_label,
            color=Colors.DANGER if danger else Colors.ACCENT,
            weight=Font.SEMIBOLD,
        ),
        on_click=handle_confirm,
    )

    dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text(title, size=Font.SIZE_LARGE, weight=Font.BOLD),
        content=ft.Text(message, size=Font.SIZE_BODY, color=Colors.TEXT_SECONDARY),
        actions=[
            ft.TextButton(content=ft.Text("Cancel", color=Colors.TEXT_SECONDARY),
                          on_click=handle_cancel),
            confirm_btn,
        ],
        actions_alignment=ft.MainAxisAlignment.END,
        shape=ft.RoundedRectangleBorder(radius=Radius.LG),
    )

    page.open(dialog)
