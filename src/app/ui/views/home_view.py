"""
Tela Home (rota "home") — visão geral enxuta.

Conforme pedido: resumo rápido + atalhos. Sem excesso.

Contém:
  - Saudação com o nome do usuário
  - 3 números-chave do mês: saldo, gasto, próxima conta
  - Shortcuts para as ações mais comuns (navegam para outras telas)

Recebe `on_navigate` para os atalhos levarem o usuário às telas certas.
"""

from datetime import date, timedelta
from decimal import Decimal
from typing import Callable

import flet as ft

from app.database.connection import get_session
from app.database.models import User
from app.services import bill_service
from app.services import income_service
from app.services import transaction_service as tx_service
from app.ui.theme import Colors, Font, Radius, Spacing, format_brl


class HomeView:
    def __init__(self, page: ft.Page, user: User, on_navigate: Callable[[str], None]):
        self.page = page
        self.user = user
        self.on_navigate = on_navigate

    def build(self) -> ft.Control:
        today = date.today()

        # --- Coleta os números do resumo ---
        first = today.replace(day=1)
        next_month = (first + timedelta(days=32)).replace(day=1)
        last = next_month - timedelta(days=1)

        with get_session() as s:
            expenses = tx_service.search_transactions(
                s, self.user.id, kind="expense", start=first, end=last
            )
            # Incomes registradas como transação (ex: "+500 freela" pelo bot)
            income_txs = tx_service.search_transactions(
                s, self.user.id, kind="income", start=first, end=last
            )
            # Renda principal definida no card do dashboard (tabela Income)
            income_principal = income_service.get_current_month_income(s, self.user.id, today)
            unpaid_bills = bill_service.list_bills(s, self.user.id, only_unpaid=True)
            next_bill = unpaid_bills[0] if unpaid_bills else None
            next_bill_data = (
                (next_bill.description, next_bill.amount, next_bill.due_date)
                if next_bill else None
            )

        total_exp = sum((t.amount for t in expenses), Decimal("0"))
        # Renda total = renda principal (tabela Income) + entradas avulsas (transações)
        total_inc = income_principal + sum((t.amount for t in income_txs), Decimal("0"))
        saldo = total_inc - total_exp

        # --- Saudação ---
        greeting = f"Hello, {self.user.name.split()[0]}"
        subtitle = today.strftime("Today is %m/%d/%Y")

        header = ft.Column([
            ft.Text(greeting, size=Font.SIZE_HUGE, weight=Font.BOLD, color=Colors.TEXT_PRIMARY),
            ft.Text(subtitle, size=Font.SIZE_BODY, color=Colors.TEXT_SECONDARY),
        ], spacing=Spacing.XS)

        # --- Resumo rápido: 3 mini-cards ---
        summary = ft.Row([
            self._summary_card("Month balance", format_brl(saldo),
                               Colors.SUCCESS if saldo >= 0 else Colors.DANGER),
            self._summary_card("Month spending", format_brl(total_exp), Colors.TEXT_PRIMARY),
            self._next_bill_card(next_bill_data, today),
        ], spacing=Spacing.MD)

        # --- Shortcuts ---
        shortcuts_title = ft.Text("Shortcuts", size=Font.SIZE_LARGE, weight=Font.SEMIBOLD,
                                  color=Colors.TEXT_PRIMARY)
        shortcuts = ft.Row([
            self._shortcut("View dashboard", ft.Icons.GRID_VIEW_OUTLINED, "dashboard"),
            self._shortcut("History", ft.Icons.INVENTORY_2_OUTLINED, "transactions"),
            self._shortcut("Bills", ft.Icons.RECEIPT_LONG_OUTLINED, "bills"),
            self._shortcut("Categorys", ft.Icons.LABEL_OUTLINE, "categories"),
        ], spacing=Spacing.MD, wrap=True)

        return ft.Container(
            content=ft.Column([
                header,
                ft.Container(height=Spacing.LG),
                summary,
                ft.Container(height=Spacing.LG),
                shortcuts_title,
                shortcuts,
            ], spacing=Spacing.MD, scroll=ft.ScrollMode.AUTO, expand=True),
            padding=ft.padding.all(Spacing.XL), expand=True, bgcolor=Colors.BG_APP,
        )

    def _summary_card(self, label: str, value: str, color: str) -> ft.Control:
        return ft.Container(
            content=ft.Column([
                ft.Text(label, size=Font.SIZE_SMALL, color=Colors.TEXT_SECONDARY, weight=Font.MEDIUM),
                ft.Text(value, size=Font.SIZE_TITLE, weight=Font.BOLD, color=color),
            ], spacing=Spacing.XS),
            bgcolor=Colors.BG_CARD, border=ft.border.all(1, Colors.BORDER),
            border_radius=Radius.LG, padding=Spacing.LG, expand=True,
        )

    def _next_bill_card(self, bill_data, today: date) -> ft.Control:
        if bill_data is None:
            value = "—"
            sub = "No pending bills"
            color = Colors.TEXT_TERTIARY
        else:
            desc, amount, due = bill_data
            value = format_brl(amount)
            dias = (due - today).days
            if dias < 0:
                sub = f"{desc} — overdue"
                color = Colors.DANGER
            elif dias == 0:
                sub = f"{desc} — due today"
                color = Colors.DANGER
            else:
                sub = f"{desc} — in {dias} day(s)"
                color = Colors.TEXT_PRIMARY

        return ft.Container(
            content=ft.Column([
                ft.Text("Next bill", size=Font.SIZE_SMALL, color=Colors.TEXT_SECONDARY,
                        weight=Font.MEDIUM),
                ft.Text(value, size=Font.SIZE_TITLE, weight=Font.BOLD, color=color),
                ft.Text(sub, size=Font.SIZE_SMALL, color=Colors.TEXT_TERTIARY,
                        no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS),
            ], spacing=Spacing.XS),
            bgcolor=Colors.BG_CARD, border=ft.border.all(1, Colors.BORDER),
            border_radius=Radius.LG, padding=Spacing.LG, expand=True,
        )

    def _shortcut(self, label: str, icon: str, route: str) -> ft.Control:
        return ft.Container(
            content=ft.Column([
                ft.Icon(icon, size=28, color=Colors.ACCENT),
                ft.Text(label, size=Font.SIZE_BODY, color=Colors.TEXT_PRIMARY, weight=Font.MEDIUM),
            ], spacing=Spacing.SM, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            width=160, height=110,
            bgcolor=Colors.BG_CARD, border=ft.border.all(1, Colors.BORDER),
            border_radius=Radius.LG, padding=Spacing.LG,
            alignment=ft.alignment.center, ink=True,
            on_click=lambda e, r=route: self.on_navigate(r),
        )
