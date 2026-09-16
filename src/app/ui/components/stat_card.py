"""
StatCard: card grande com label e valor monetário.

Usado três vezes no topo do dashboard:
  - "Available  R$ 2.420,00"
  - "Bills      R$ 1.950,00"
  - "Income     R$ 4.350,00"

Opcionalmente, um card pode ter um botão de editar (lápis) no canto
superior direito — usado no card de Income para ajuste rápido.
"""

from typing import Callable, Optional

import flet as ft

from app.ui.theme import Colors, Font, Radius, Spacing, format_brl_masked


def build_stat_card(
    label: str,
    amount,                  # Decimal | float | int
    on_edit: Optional[Callable[[], None]] = None,
    hidden: bool = False,    # se True, mostra '••••••' no lugar do valor
) -> ft.Container:
    """
    Constrói um card de estatística: label + valor.

    Se `on_edit` for fornecido, mostra um pequeno botão de lápis no canto
    que dispara esse callback ao ser clicado.
    """

    # Linha do topo: label à esquerda e (opcional) botão de editar à direita
    top_row_controls: list[ft.Control] = [
        ft.Text(label, size=Font.SIZE_BODY, weight=Font.SEMIBOLD, color=Colors.TEXT_PRIMARY),
    ]
    if on_edit is not None:
        top_row_controls.append(ft.Container(expand=True))  # empurra o botão p/ direita
        top_row_controls.append(
            ft.IconButton(
                icon=ft.Icons.EDIT_OUTLINED,
                icon_size=16,
                icon_color=Colors.TEXT_TERTIARY,
                tooltip="Ajustar",
                on_click=lambda e: on_edit(),
                style=ft.ButtonStyle(padding=0),
            )
        )

    return ft.Container(
        content=ft.Column(
            [
                ft.Row(
                    top_row_controls,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    height=24,
                ),
                ft.Container(
                    content=ft.Text(
                        format_brl_masked(amount, hidden),
                        size=Font.SIZE_HUGE,
                        weight=Font.BOLD,
                        color=Colors.TEXT_PRIMARY,
                    ),
                    padding=ft.padding.symmetric(vertical=Spacing.SM),
                ),
            ],
            spacing=0,
            alignment=ft.MainAxisAlignment.START,
        ),
        bgcolor=Colors.BG_CARD,
        border=ft.border.all(1, Colors.BORDER),
        border_radius=Radius.LG,
        padding=Spacing.LG,
        expand=True,
    )
