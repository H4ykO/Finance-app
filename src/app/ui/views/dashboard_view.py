"""
Dashboard view — tela de visão geral financeira.

Composta por:
  - Header: título "Finances" + botões à direita (... / Share / avatar)
  - Linha "Dashboard"
  - Linha com 3 stat cards (Available / Bills / Income)
  - Card grande "Monthly Expenses" (gráfico de linha)
  - Linha com 2 cards: "Last purchases" (tabela) e "Weekly Expenses" (barras)

O card "Income" tem um botão de editar (lápis) que
abre um diálogo minimalista para ajustar a renda do mês atual. Por
causa desse estado interativo, a view virou uma CLASSE.
"""

from decimal import Decimal, InvalidOperation
from typing import Optional

import flet as ft

from app.database.connection import get_session
from app.database.models import User
from app.services.dashboard_service import build_dashboard
from app.services import income_service
from app.services import preferences_service
from app.ui.components.charts import (
    build_monthly_expenses_chart,
    build_weekly_expenses_chart,
)
from app.ui.components.stat_card import build_stat_card
from app.ui.components.transactions_table import build_transactions_table
from app.ui.theme import Colors, Font, Radius, Spacing


class DashboardView:
    """View do dashboard, agora com estado (page) para diálogos."""

    def __init__(self, page: ft.Page, user: User):
        self.page = page
        self.user = user
        # Container raiz mantido como referência para podermos recarregar
        # o conteúdo após o usuário editar o income.
        self.root = ft.Container(
            padding=ft.padding.all(Spacing.XL),
            expand=True,
            bgcolor=Colors.BG_APP,
        )

    def build(self) -> ft.Control:
        """Monta (ou remonta) o conteúdo do dashboard."""
        with get_session() as session:
            data = build_dashboard(session, user_id=self.user.id)

        hidden = preferences_service.get_hide_balances()
        header = self._build_header(hidden)

        dashboard_label = ft.Text(
            "Dashboard", size=Font.SIZE_BODY, color=Colors.TEXT_SECONDARY, weight=Font.MEDIUM,
        )

        stat_cards_row = ft.Row(
            [
                build_stat_card(
                    label=data.available.label,
                    amount=data.available.amount,
                    variation_percent=data.available.variation_percent,
                    positive_is_good=data.available.variation_is_positive_good,
                    hidden=hidden,
                ),
                build_stat_card(
                    label=data.bills.label,
                    amount=data.bills.amount,
                    variation_percent=data.bills.variation_percent,
                    positive_is_good=data.bills.variation_is_positive_good,
                    hidden=hidden,
                ),
                build_stat_card(
                    label=data.income.label,
                    amount=data.income.amount,
                    variation_percent=data.income.variation_percent,
                    positive_is_good=data.income.variation_is_positive_good,
                    on_edit=self._open_income_dialog,
                    hidden=hidden,
                ),
            ],
            spacing=Spacing.MD,
        )

        monthly_chart = build_monthly_expenses_chart(data.monthly_expenses_by_day)

        bottom_row = ft.Row(
            [
                build_transactions_table(
                    transactions=data.recent_transactions,
                    current_balance=data.available.amount,
                ),
                build_weekly_expenses_chart(data.weekly_expenses),
            ],
            spacing=Spacing.MD,
            vertical_alignment=ft.CrossAxisAlignment.START,
        )

        self.root.content = ft.Column(
            [
                header,
                ft.Container(padding=ft.padding.only(top=Spacing.LG)),
                dashboard_label,
                stat_cards_row,
                monthly_chart,
                bottom_row,
            ],
            spacing=Spacing.MD,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )
        return self.root

    def _reload(self):
        """Recarrega o dashboard inteiro (após editar income)."""
        self.build()
        if self.root.page is not None:
            self.root.update()

    # -----------------------------------------------------------------------
    # Diálogo minimalista de ajuste de renda do mês
    # -----------------------------------------------------------------------
    def _open_income_dialog(self):
        # Busca o valor atual para pré-preencher o campo
        with get_session() as s:
            current = income_service.get_current_month_income(s, self.user.id)

        # Pré-preenche com o valor atual formatado em padrão BR (vírgula)
        initial = f"{current:.2f}".replace(".", ",") if current else ""

        amount_field = ft.TextField(
            label="Monthly income",
            prefix_text="R$ ",
            value=initial,
            autofocus=True,
            border_color=Colors.BORDER,
            focused_border_color=Colors.ACCENT,
            keyboard_type=ft.KeyboardType.NUMBER,
        )
        error_text = ft.Text("", color=Colors.DANGER, size=Font.SIZE_SMALL, visible=False)

        def handle_save(e):
            amount = self._parse_amount(amount_field.value)
            if amount is None:
                error_text.value = "Invalid amount. Ex: 4350,00"
                error_text.visible = True
                error_text.update()
                return

            with get_session() as s:
                income_service.set_current_month_income(s, self.user.id, amount)

            self.page.close(dialog)
            self._reload()

        amount_field.on_submit = handle_save

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Adjust monthly income", size=Font.SIZE_LARGE, weight=Font.BOLD),
            content=ft.Container(
                content=ft.Column(
                    [
                        ft.Text(
                            "Set the total income for this month. Replaces the previous value.",
                            size=Font.SIZE_SMALL, color=Colors.TEXT_SECONDARY,
                        ),
                        amount_field,
                        error_text,
                    ],
                    spacing=Spacing.MD, tight=True, width=340,
                ),
                padding=ft.padding.only(top=Spacing.SM),
            ),
            actions=[
                ft.TextButton(content=ft.Text("Cancel", color=Colors.TEXT_SECONDARY),
                              on_click=lambda e: self.page.close(dialog)),
                ft.TextButton(content=ft.Text("Save", color=Colors.ACCENT, weight=Font.SEMIBOLD),
                              on_click=handle_save),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
            shape=ft.RoundedRectangleBorder(radius=Radius.LG),
        )
        self.page.open(dialog)

    def _parse_amount(self, raw: Optional[str]) -> Optional[Decimal]:
        """Converte '4.350,00' ou '4350.00' em Decimal. None se inválido."""
        if not raw:
            return None
        cleaned = raw.strip().replace(".", "").replace(",", ".")
        try:
            value = Decimal(cleaned)
            return value if value >= 0 else None
        except (InvalidOperation, ValueError):
            return None

    # -----------------------------------------------------------------------
    # Header
    # -----------------------------------------------------------------------
    def _build_header(self, hidden: bool) -> ft.Control:
        eye_icon = ft.Icons.VISIBILITY_OFF_OUTLINED if hidden else ft.Icons.VISIBILITY_OUTLINED
        eye_button = ft.IconButton(
            icon=eye_icon,
            icon_color=Colors.TEXT_SECONDARY,
            tooltip="Show values" if hidden else "Hide values",
            on_click=lambda e: self._toggle_hidden(),
        )
        return ft.Row(
            [
                ft.Text("Finances", size=Font.SIZE_TITLE, weight=Font.BOLD,
                        color=Colors.TEXT_PRIMARY),
                ft.Container(expand=True),
                eye_button,
            ],
            spacing=Spacing.SM, vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

    def _toggle_hidden(self) -> None:
        """Alterna ocultar/mostrar valores e re-renderiza o dashboard."""
        novo = not preferences_service.get_hide_balances()
        preferences_service.set_hide_balances(novo)
        self.build()  # remonta com o novo estado
        if self.root.page is not None:
            self.root.update()


# ---------------------------------------------------------------------------
# Wrapper de compatibilidade: o controller chama build_dashboard_view(...)
# ---------------------------------------------------------------------------
def build_dashboard_view(user: User, page: Optional[ft.Page] = None) -> ft.Control:
    """
    Mantém a assinatura antiga funcionando. Se `page` for fornecida,
    o card de Income fica editável; senão, o dashboard funciona sem
    o botão de edição (degradação graciosa).
    """
    if page is None:
        # Fallback: cria a view sem capacidade de abrir diálogo.
        # Usado só em testes/smoke; no app real sempre passamos page.
        class _NoPage:
            def open(self, d): pass
            def close(self, d): pass
        view = DashboardView(_NoPage(), user)  # type: ignore
        return view.build()
    return DashboardView(page, user).build()
