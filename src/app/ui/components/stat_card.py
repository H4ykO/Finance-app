"""
StatCard: card grande com label, valor monetário e variação percentual.

Usado três vezes no topo do dashboard:
  - "Available  R$ 2.420,00  +20% month over month"
  - "Bills      R$ 1.950,00  +33% month over month"
  - "Income     R$ 4.350,00  -8% month over month"

Opcionalmente, um card pode ter um botão de editar (lápis) no canto
superior direito — usado no card de Income para ajuste rápido.
"""

from typing import Callable, Optional

import flet as ft

from app.ui.theme import Colors, Font, Radius, Spacing, format_brl


def build_stat_card(
    label: str,
    amount,                  # Decimal | float | int
    variation_percent: Optional[float],
    positive_is_good: bool = True,
    on_edit: Optional[Callable[[], None]] = None,
) -> ft.Container:
    """
    Constrói um card de estatística.

    Lógica de cor da variação:
      - Se positive_is_good=True (Available/Income): + verde, - vermelho
      - Se positive_is_good=False (Bills, na prática): + vermelho, - verde
      - Se variation_percent é None (sem histórico): mostra "—" cinza

    Se `on_edit` for fornecido, mostra um pequeno botão de lápis no canto
    que dispara esse callback ao ser clicado.
    """

    # Decide o texto e a cor da linha de variação
    if variation_percent is None:
        variation_text = "— no previous history"
        variation_color = Colors.TEXT_TERTIARY
    else:
        sign = "+" if variation_percent >= 0 else ""
        variation_text = f"{sign}{variation_percent:.0f}% month over month"

        is_positive_value = variation_percent >= 0
        is_good = is_positive_value if positive_is_good else not is_positive_value
        variation_color = Colors.SUCCESS if is_good else Colors.DANGER

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
                        format_brl(amount),
                        size=Font.SIZE_HUGE,
                        weight=Font.BOLD,
                        color=Colors.TEXT_PRIMARY,
                    ),
                    padding=ft.padding.symmetric(vertical=Spacing.SM),
                ),
                ft.Text(
                    variation_text,
                    size=Font.SIZE_SMALL,
                    color=variation_color,
                    weight=Font.MEDIUM,
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
