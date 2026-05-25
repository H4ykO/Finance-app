"""
Tela de Analytics (rota "analytics").

Abas por período: Daily, Weekly, Monthly, Yearly.

Em cada aba (exceto Yearly):
  - um resumo com o total gasto e a comparação com o período anterior
  - um gráfico de pizza dos gastos por categoria

Na aba Yearly:
  - barras de gastos vs renda por mês ao longo do ano

A aba "Investments" do plano original fica para depois (precisaria de
um cadastro de investimentos que ainda não existe). A estrutura de abas
já comporta adicioná-la no futuro.
"""

from datetime import date

import flet as ft

from app.database.connection import get_session
from app.database.models import User
from app.services import analytics_service as an
from app.ui.components.charts import (
    build_category_pie_chart,
    build_monthly_comparison_chart,
)
from app.ui.theme import Colors, Font, Radius, Spacing, format_brl


# Rótulos amigáveis de cada período
PERIOD_LABELS = {
    "daily": "today",
    "weekly": "this week",
    "monthly": "this month",
}


class AnalyticsView:
    def __init__(self, page: ft.Page, user: User):
        self.page = page
        self.user = user
        self.today = date.today()

    def build(self) -> ft.Control:
        tabs = ft.Tabs(
            selected_index=2,  # começa em Monthly (o mais útil no dia a dia)
            animation_duration=200,
            label_color=Colors.TEXT_PRIMARY,
            unselected_label_color=Colors.TEXT_TERTIARY,
            indicator_color=Colors.ACCENT,
            tabs=[
                ft.Tab(text="Daily", content=self._period_tab("daily")),
                ft.Tab(text="Weekly", content=self._period_tab("weekly")),
                ft.Tab(text="Monthly", content=self._period_tab("monthly")),
                ft.Tab(text="Yearly", content=self._yearly_tab()),
            ],
            expand=True,
        )

        return ft.Container(
            content=ft.Column([
                ft.Text("Analytics", size=Font.SIZE_TITLE, weight=Font.BOLD,
                        color=Colors.TEXT_PRIMARY),
                ft.Container(height=Spacing.SM),
                tabs,
            ], spacing=Spacing.MD, expand=True),
            padding=ft.padding.all(Spacing.XL), expand=True, bgcolor=Colors.BG_APP,
        )

    # -----------------------------------------------------------------------
    # Aba de período (daily/weekly/monthly)
    # -----------------------------------------------------------------------
    def _period_tab(self, kind: str) -> ft.Control:
        with get_session() as s:
            start, end = an.period_bounds(kind, self.today)
            slices = an.expenses_by_category(s, self.user.id, start, end)
            comparison = an.compare_expenses(s, self.user.id, kind, self.today)

        summary = self._summary_row(kind, comparison)
        pie = build_category_pie_chart(
            slices, title=f"Spending by category ({PERIOD_LABELS[kind]})"
        )

        return ft.Container(
            content=ft.Column([
                ft.Container(height=Spacing.MD),
                summary,
                pie,
            ], spacing=Spacing.MD, scroll=ft.ScrollMode.AUTO),
            padding=ft.padding.only(top=Spacing.SM),
        )

    def _summary_row(self, kind: str, comparison: an.PeriodComparison) -> ft.Control:
        # Card do total + card da variação
        total_card = ft.Container(
            content=ft.Column([
                ft.Text(f"Total spent ({PERIOD_LABELS[kind]})", size=Font.SIZE_SMALL,
                        color=Colors.TEXT_SECONDARY, weight=Font.MEDIUM),
                ft.Text(format_brl(comparison.current), size=Font.SIZE_TITLE,
                        weight=Font.BOLD, color=Colors.TEXT_PRIMARY),
            ], spacing=Spacing.XS),
            bgcolor=Colors.BG_CARD, border=ft.border.all(1, Colors.BORDER),
            border_radius=Radius.LG, padding=Spacing.LG, expand=True,
        )

        # Variação vs período anterior
        if comparison.percent_change is None:
            var_text = "— no previous period"
            var_color = Colors.TEXT_TERTIARY
        else:
            # Para gastos: subir é ruim (vermelho), cair é bom (verde)
            up = comparison.percent_change >= 0
            sign = "+" if up else ""
            var_text = f"{sign}{comparison.percent_change:.0f}% vs previous"
            var_color = Colors.DANGER if up else Colors.SUCCESS

        var_card = ft.Container(
            content=ft.Column([
                ft.Text("Change", size=Font.SIZE_SMALL, color=Colors.TEXT_SECONDARY,
                        weight=Font.MEDIUM),
                ft.Text(var_text, size=Font.SIZE_LARGE, weight=Font.BOLD, color=var_color),
                ft.Text(f"Previous: {format_brl(comparison.previous)}",
                        size=Font.SIZE_SMALL, color=Colors.TEXT_TERTIARY),
            ], spacing=Spacing.XS),
            bgcolor=Colors.BG_CARD, border=ft.border.all(1, Colors.BORDER),
            border_radius=Radius.LG, padding=Spacing.LG, expand=True,
        )

        return ft.Row([total_card, var_card], spacing=Spacing.MD)

    # -----------------------------------------------------------------------
    # Aba anual
    # -----------------------------------------------------------------------
    def _yearly_tab(self) -> ft.Control:
        with get_session() as s:
            points = an.monthly_series(s, self.user.id, self.today.year)

        total_exp = sum((p.expenses for p in points), __import__("decimal").Decimal("0"))
        total_inc = sum((p.income for p in points), __import__("decimal").Decimal("0"))

        summary = ft.Row([
            self._mini_card(f"Total spent ({self.today.year})", format_brl(total_exp),
                            Colors.TEXT_PRIMARY),
            self._mini_card(f"Total income ({self.today.year})", format_brl(total_inc),
                            Colors.SUCCESS),
        ], spacing=Spacing.MD)

        chart = build_monthly_comparison_chart(
            points, title=f"Monthly expenses & income ({self.today.year})"
        )

        return ft.Container(
            content=ft.Column([
                ft.Container(height=Spacing.MD),
                summary,
                chart,
            ], spacing=Spacing.MD, scroll=ft.ScrollMode.AUTO),
            padding=ft.padding.only(top=Spacing.SM),
        )

    def _mini_card(self, label: str, value: str, color: str) -> ft.Control:
        return ft.Container(
            content=ft.Column([
                ft.Text(label, size=Font.SIZE_SMALL, color=Colors.TEXT_SECONDARY,
                        weight=Font.MEDIUM),
                ft.Text(value, size=Font.SIZE_TITLE, weight=Font.BOLD, color=color),
            ], spacing=Spacing.XS),
            bgcolor=Colors.BG_CARD, border=ft.border.all(1, Colors.BORDER),
            border_radius=Radius.LG, padding=Spacing.LG, expand=True,
        )
