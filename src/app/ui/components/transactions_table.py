"""
Tabela de últimas compras (canto inferior esquerdo do dashboard).

Colunas: Source / Value / Difference.
"Source" é a descrição/estabelecimento da compra.
"Value" é o valor da compra individual.
"Difference" é o saldo restante após a compra (running balance).
"""

from decimal import Decimal

import flet as ft

from app.ui.theme import Colors, Font, Radius, Spacing, format_brl


def build_transactions_table(transactions: list, current_balance: Decimal) -> ft.Container:
    """
    Constrói o card "Last purchases".

    `transactions` é uma lista de objetos Transaction (do banco).
    `current_balance` é o saldo atual (Available), usado para calcular
    o "Difference" — o que sobraria se desfizéssemos cada compra.

    Lógica da coluna Difference:
      - Para a transação mais recente, Difference = saldo atual
      - Para cada anterior, somamos os gastos das compras posteriores
        (como se voltássemos no tempo)
    """
    if not transactions:
        return ft.Container(
            content=ft.Column(
                [
                    ft.Text(
                        "Last purchases",
                        size=Font.SIZE_LARGE,
                        weight=Font.SEMIBOLD,
                    ),
                    ft.Container(
                        content=ft.Text(
                            "No purchases recorded yet.",
                            color=Colors.TEXT_TERTIARY,
                            size=Font.SIZE_BODY,
                        ),
                        alignment=ft.alignment.center,
                        expand=True,
                    ),
                ],
                spacing=Spacing.MD,
                expand=True,
            ),
            bgcolor=Colors.BG_CARD,
            border=ft.border.all(1, Colors.BORDER),
            border_radius=Radius.LG,
            padding=Spacing.LG,
            height=380,
            expand=True,
        )

    # Calcula o running balance de trás pra frente.
    # Idéia: a transação MAIS RECENTE deixa o saldo atual; antes dela,
    # tínhamos saldo + valor dela; antes da anterior, saldo + as duas... etc.
    running = current_balance
    differences: list[Decimal] = []
    for tx in transactions:
        differences.append(running)
        # Apenas despesas afetam o saldo "para frente"
        if tx.kind == "expense":
            running = running + tx.amount
        else:
            running = running - tx.amount

    # Cabeçalho da tabela
    header = ft.Row(
        [
            _cell("Source", color=Colors.TEXT_TERTIARY, weight=Font.MEDIUM, expand=3),
            _cell("Value", color=Colors.TEXT_TERTIARY, weight=Font.MEDIUM, expand=2, align_right=True),
            _cell("Difference", color=Colors.TEXT_TERTIARY, weight=Font.MEDIUM, expand=2, align_right=True),
        ],
    )

    # Cada linha: descrição + valor + diferença
    rows: list[ft.Control] = []
    for tx, diff in zip(transactions, differences):
        rows.append(
            ft.Container(
                content=ft.Row(
                    [
                        _cell(tx.description, expand=3),
                        _cell(format_brl(tx.amount), expand=2, align_right=True),
                        _cell(format_brl(diff), expand=2, align_right=True),
                    ],
                ),
                padding=ft.padding.symmetric(vertical=Spacing.SM),
                # Borda inferior sutil — separa visualmente as linhas
                border=ft.border.only(bottom=ft.BorderSide(1, Colors.DIVIDER)),
            )
        )

    return ft.Container(
        content=ft.Column(
            [
                ft.Text(
                    "Last purchases",
                    size=Font.SIZE_LARGE,
                    weight=Font.SEMIBOLD,
                    color=Colors.TEXT_PRIMARY,
                ),
                ft.Container(padding=ft.padding.only(top=Spacing.SM)),
                header,
                # Container com scroll, caso passem do limite vertical
                ft.Column(rows, scroll=ft.ScrollMode.AUTO, expand=True, spacing=0),
            ],
            spacing=Spacing.SM,
            expand=True,
        ),
        bgcolor=Colors.BG_CARD,
        border=ft.border.all(1, Colors.BORDER),
        border_radius=Radius.LG,
        padding=Spacing.LG,
        height=380,
        expand=True,
    )


def _cell(
    text: str,
    color: str = Colors.TEXT_PRIMARY,
    weight: ft.FontWeight = Font.REGULAR,
    expand: int = 1,
    align_right: bool = False,
) -> ft.Control:
    """Helper para uma célula de tabela com formatação consistente."""
    return ft.Container(
        content=ft.Text(
            text,
            size=Font.SIZE_BODY,
            color=color,
            weight=weight,
            # No-wrap para que valores monetários longos não quebrem
            no_wrap=True,
            overflow=ft.TextOverflow.ELLIPSIS,
            text_align=ft.TextAlign.RIGHT if align_right else ft.TextAlign.LEFT,
        ),
        expand=expand,
        alignment=ft.alignment.center_right if align_right else ft.alignment.center_left,
    )
