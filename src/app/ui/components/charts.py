"""
Componentes de gráfico — linha (Monthly Expenses) e barras (Week Expenses).

Flet expõe gráficos nativos via `ft.LineChart` e `ft.BarChart`, que
são wrappers sobre o pacote fl_chart do Flutter. A API é declarativa:
você descreve séries, eixos, grids, e o Flet renderiza.
"""

from datetime import date
from decimal import Decimal

import flet as ft

from app.ui.theme import Colors, Font, Radius, Spacing


# ---------------------------------------------------------------------------
# Card-base: caixa branca arredondada com título — reutilizada nos dois gráficos
# ---------------------------------------------------------------------------
def _chart_card(title: str, content: ft.Control, height: int = 360) -> ft.Container:
    """Wrapper visual comum dos gráficos."""
    return ft.Container(
        content=ft.Column(
            [
                ft.Text(
                    title,
                    size=Font.SIZE_LARGE,
                    weight=Font.SEMIBOLD,
                    color=Colors.TEXT_PRIMARY,
                ),
                ft.Container(content=content, expand=True),
            ],
            spacing=Spacing.MD,
            expand=True,
        ),
        bgcolor=Colors.BG_CARD,
        border=ft.border.all(1, Colors.BORDER),
        border_radius=Radius.LG,
        padding=Spacing.LG,
        height=height,
        expand=True,
    )


# ---------------------------------------------------------------------------
# Gráfico de linha — gastos por dia no mês atual
# ---------------------------------------------------------------------------
def build_monthly_expenses_chart(
    data: list[tuple[date, Decimal]],
) -> ft.Container:
    """
    Linha escura com gradiente suave embaixo.

    `data` é uma lista de (dia, total_gasto). Convertemos para
    DataPoint(x=dia_do_mes, y=total).
    """
    if not data:
        # Placeholder bonito quando ainda não há dados
        return _chart_card(
            "Monthly Expenses",
            ft.Container(
                content=ft.Text(
                    "No transactions this month.",
                    color=Colors.TEXT_TERTIARY,
                    size=Font.SIZE_BODY,
                ),
                alignment=ft.alignment.center,
                expand=True,
            ),
        )

    # Pontos no formato que o Flet espera
    points = [
        ft.LineChartDataPoint(x=d.day, y=float(total))
        for d, total in data
    ]

    # Faixas dos eixos — calculamos a partir dos próprios dados
    # para que o gráfico se ajuste bem ao range existente
    min_y = 0.0
    max_y = max(float(total) for _, total in data) * 1.15  # 15% de folga no topo
    min_x = min(d.day for d, _ in data)
    max_x = max(d.day for d, _ in data)

    # Série principal — linha preta com área preenchida abaixo
    series = ft.LineChartData(
        data_points=points,
        stroke_width=2,
        color=Colors.CHART_LINE,
        curved=False,
        stroke_cap_round=True,
        # Preenche a área abaixo da linha com gradiente sutil
        below_line_bgcolor=Colors.CHART_GRADIENT + "33",  # "33" = alpha ~20%
        below_line_gradient=ft.LinearGradient(
            begin=ft.alignment.top_center,
            end=ft.alignment.bottom_center,
            colors=[
                Colors.CHART_GRADIENT + "55",
                Colors.CHART_GRADIENT + "00",
            ],
        ),
        # Pontos visíveis apenas nas pontas — limpo
        point=False,
    )

    chart = ft.LineChart(
        data_series=[series],
        # Grid horizontal sutil — separação visual entre faixas de valor
        horizontal_grid_lines=ft.ChartGridLines(
            interval=max_y / 4 if max_y > 0 else 1,
            color=Colors.DIVIDER,
            width=1,
        ),
        # Eixo Y à esquerda com labels formatados
        left_axis=ft.ChartAxis(
            labels_size=50,
            labels=_y_axis_labels(min_y, max_y, steps=5),
        ),
        # Eixo X embaixo: dias do mês
        bottom_axis=ft.ChartAxis(
            labels_size=30,
            labels=_x_axis_labels(data),
        ),
        # Sem borda colorida nas laterais
        border=ft.border.all(0, "transparent"),
        # Faixa Y começa em 0; faixa X usa min/max dos dados
        min_y=min_y,
        max_y=max_y,
        min_x=min_x,
        max_x=max_x,
        expand=True,
        # Animação suave quando os dados mudam
        animate=1000,
    )

    return _chart_card("Monthly Expenses", chart, height=380)


def _y_axis_labels(min_y: float, max_y: float, steps: int = 5) -> list[ft.ChartAxisLabel]:
    """Gera labels para o eixo Y dividindo o range em N passos."""
    if max_y <= min_y:
        return []
    labels = []
    step = (max_y - min_y) / steps
    for i in range(steps + 1):
        value = min_y + step * i
        labels.append(
            ft.ChartAxisLabel(
                value=value,
                label=ft.Text(
                    _format_short_currency(value),
                    size=Font.SIZE_SMALL,
                    color=Colors.TEXT_TERTIARY,
                ),
            )
        )
    return labels


def _x_axis_labels(data: list[tuple[date, Decimal]]) -> list[ft.ChartAxisLabel]:
    """
    Labels do eixo X. Se temos muitos dias, mostramos só alguns
    para não poluir.
    """
    if not data:
        return []

    days = [d for d, _ in data]
    # Se temos até 8 pontos mostramos todos; senão pulamos
    step = max(1, len(days) // 7)
    labels = []
    for i in range(0, len(days), step):
        d = days[i]
        labels.append(
            ft.ChartAxisLabel(
                value=d.day,
                label=ft.Text(
                    str(d.day),
                    size=Font.SIZE_SMALL,
                    color=Colors.TEXT_TERTIARY,
                ),
            )
        )
    return labels


def _format_short_currency(value: float) -> str:
    """Formata número curto para eixo: 1500 -> 'R$ 1,5k', 12000 -> 'R$ 12k'."""
    if value >= 1000:
        return f"R$ {value/1000:.1f}k".replace(".", ",")
    return f"R$ {value:.0f}"


# ---------------------------------------------------------------------------
# Gráfico de barras — gastos semanais
# ---------------------------------------------------------------------------
def build_weekly_expenses_chart(
    data: list[tuple[date, Decimal]],
) -> ft.Container:
    """
    Barras verticais pretas — total gasto em cada uma das últimas N semanas.

    `data` é lista de (segunda-feira_da_semana, total).
    """
    if not data:
        return _chart_card(
            "Weekly Expenses",
            ft.Container(
                content=ft.Text(
                    "Sem dados ainda.",
                    color=Colors.TEXT_TERTIARY,
                    size=Font.SIZE_BODY,
                ),
                alignment=ft.alignment.center,
                expand=True,
            ),
            height=380,
        )

    # Cada grupo de barras é um BarChartGroup com uma BarChartRod dentro
    groups = []
    for i, (week_start, total) in enumerate(data):
        groups.append(
            ft.BarChartGroup(
                x=i,
                bar_rods=[
                    ft.BarChartRod(
                        from_y=0,
                        to_y=float(total),
                        width=18,
                        color=Colors.CHART_BAR,
                        border_radius=Radius.SM,
                        # Tooltip ao passar o mouse: data e valor
                        tooltip=f"{week_start.strftime('%d/%m')}: R$ {total:,.2f}",
                    )
                ],
            )
        )

    max_y = max(float(t) for _, t in data) * 1.15 if data else 100

    # Labels do eixo X: dia/mês curto da segunda-feira da semana
    x_labels = []
    for i, (week_start, _) in enumerate(data):
        x_labels.append(
            ft.ChartAxisLabel(
                value=i,
                label=ft.Text(
                    week_start.strftime("%d/%m"),
                    size=Font.SIZE_TINY,
                    color=Colors.TEXT_TERTIARY,
                ),
            )
        )

    chart = ft.BarChart(
        bar_groups=groups,
        horizontal_grid_lines=ft.ChartGridLines(
            interval=max_y / 4 if max_y > 0 else 1,
            color=Colors.DIVIDER,
            width=1,
        ),
        left_axis=ft.ChartAxis(
            labels_size=50,
            labels=_y_axis_labels(0, max_y, steps=4),
        ),
        bottom_axis=ft.ChartAxis(
            labels_size=30,
            labels=x_labels,
        ),
        border=ft.border.all(0, "transparent"),
        max_y=max_y,
        min_y=0,
        expand=True,
        animate=1000,
        # Espaçamento entre grupos — barras finas com ar entre elas
        groups_space=12,
    )

    return _chart_card("Weekly Expenses", chart, height=380)


def build_category_pie_chart(slices, title: str = "Spending by category"):
    """
    Gráfico de pizza dos gastos por categoria.

    `slices` é uma lista de analytics_service.CategorySlice. Cada fatia
    usa a cor da categoria. Ao lado, uma legenda com nome, valor e %.

    Se não houver gastos, mostra um aviso amigável.
    """
    import flet as ft
    from app.ui.theme import Colors, Font, Radius, Spacing, format_brl

    if not slices:
        return _chart_card(
            title,
            ft.Container(
                content=ft.Text("No expenses in this period.",
                                size=Font.SIZE_BODY, color=Colors.TEXT_TERTIARY),
                alignment=ft.alignment.center, expand=True,
            ),
        )

    # Seções da pizza
    sections = []
    for sl in slices:
        sections.append(
            ft.PieChartSection(
                value=float(sl.total),
                color=sl.color,
                radius=70,
                # Mostra a % dentro da fatia só se for grande o suficiente
                title=f"{sl.percent:.0f}%" if sl.percent >= 8 else "",
                title_style=ft.TextStyle(size=12, color=Colors.TEXT_ON_DARK,
                                         weight=Font.BOLD),
            )
        )

    pie = ft.PieChart(sections=sections, sections_space=2, center_space_radius=35,
                      expand=True)

    # Legenda ao lado
    legend_rows = []
    for sl in slices:
        legend_rows.append(
            ft.Row([
                ft.Container(width=12, height=12, bgcolor=sl.color, border_radius=Radius.PILL),
                ft.Text(sl.category_name, size=Font.SIZE_SMALL, color=Colors.TEXT_PRIMARY,
                        expand=True),
                ft.Text(f"{format_brl(sl.total)}", size=Font.SIZE_SMALL,
                        color=Colors.TEXT_SECONDARY, weight=Font.MEDIUM),
                ft.Text(f"{sl.percent:.0f}%", size=Font.SIZE_SMALL,
                        color=Colors.TEXT_TERTIARY, width=42, text_align=ft.TextAlign.RIGHT),
            ], spacing=Spacing.SM, vertical_alignment=ft.CrossAxisAlignment.CENTER)
        )

    legend = ft.Column(legend_rows, spacing=Spacing.SM, scroll=ft.ScrollMode.AUTO,
                       expand=True)

    content = ft.Row(
        [
            ft.Container(content=pie, expand=3),
            ft.Container(content=legend, expand=2,
                         padding=ft.padding.only(left=Spacing.LG)),
        ],
        spacing=Spacing.MD, expand=True,
    )
    return _chart_card(title, content, height=380)


def build_monthly_comparison_chart(points, title: str = "Monthly expenses & income"):
    """
    Barras de gastos e renda por mês ao longo do ano.

    `points` é uma lista de analytics_service.MonthlyPoint. Para cada mês
    desenha duas barras lado a lado: gasto e renda.
    """
    import flet as ft
    from app.ui.theme import Colors, Font, format_brl

    # Filtra meses sem nenhum movimento para não poluir
    active = [p for p in points if p.expenses or p.income]
    if not active:
        return _chart_card(
            title,
            ft.Container(
                content=ft.Text("No data for this year.",
                                size=Font.SIZE_BODY, color=Colors.TEXT_TERTIARY),
                alignment=ft.alignment.center, expand=True,
            ),
        )

    max_val = max((max(float(p.expenses), float(p.income)) for p in active), default=1.0)
    if max_val <= 0:
        max_val = 1.0

    groups = []
    for i, p in enumerate(active):
        groups.append(
            ft.BarChartGroup(
                x=i,
                bar_rods=[
                    ft.BarChartRod(from_y=0, to_y=float(p.expenses), width=11,
                                   color=Colors.DARK, border_radius=3,
                                   tooltip=f"Exp {format_brl(p.expenses)}"),
                    ft.BarChartRod(from_y=0, to_y=float(p.income), width=11,
                                   color=Colors.SUCCESS, border_radius=3,
                                   tooltip=f"Inc {format_brl(p.income)}"),
                ],
            )
        )

    x_labels = [
        ft.ChartAxisLabel(value=i, label=ft.Text(p.label, size=11,
                                                 color=Colors.TEXT_TERTIARY))
        for i, p in enumerate(active)
    ]

    chart = ft.BarChart(
        bar_groups=groups,
        bottom_axis=ft.ChartAxis(labels=x_labels, labels_size=28),
        left_axis=ft.ChartAxis(
            labels=_y_axis_labels(0, max_val), labels_size=52),
        max_y=max_val * 1.15,
        expand=True,
    )
    return _chart_card(title, chart, height=360)
