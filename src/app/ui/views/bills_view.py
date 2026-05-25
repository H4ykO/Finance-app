"""
Tela de Bills / Bills (rota "bills").

Atende ao pedido: mostrar as contas a pagar detalhadas como se fossem
"compras", com opção de adicionar manualmente, remover e marcar como paga.

Layout:
  - Resumo no topo: total a pagar, total já pago no mês
  - Lista de contas, cada uma como um "cartão de compra" com:
      descrição, valor, vencimento, status (paga/pendente/atrasada)
      e ações (marcar paga / remover)
  - Botão "Add conta"

Igual à HistoryView, é uma CLASSE por causa do estado mutável.
"""

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Optional

import flet as ft

from app.database.connection import get_session
from app.database.models import User
from app.services import bill_service
from app.ui.components.dialogs import confirm_dialog
from app.ui.theme import Colors, Font, Radius, Spacing, format_brl


class BillsView:
    """View com estado para a tela de contas a pagar."""

    def __init__(self, page: ft.Page, user: User):
        self.page = page
        self.user = user

        self.list_container = ft.Column(spacing=Spacing.SM, scroll=ft.ScrollMode.AUTO, expand=True)
        self.summary_row = ft.Row(spacing=Spacing.MD)

    def build(self) -> ft.Control:
        header = ft.Row(
            [
                ft.Text("Bills", size=Font.SIZE_TITLE, weight=Font.BOLD,
                        color=Colors.TEXT_PRIMARY),
                ft.Container(expand=True),
                ft.ElevatedButton(
                    content=ft.Row(
                        [ft.Icon(ft.Icons.ADD, size=18), ft.Text("Add conta")],
                        spacing=Spacing.SM, tight=True,
                    ),
                    on_click=lambda e: self._open_add_dialog(),
                    style=ft.ButtonStyle(
                        bgcolor=Colors.DARK, color=Colors.TEXT_ON_DARK,
                        shape=ft.RoundedRectangleBorder(radius=Radius.MD),
                    ),
                    height=42,
                ),
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        self._reload()

        return ft.Container(
            content=ft.Column(
                [
                    header,
                    ft.Container(height=Spacing.SM),
                    self.summary_row,
                    ft.Container(height=Spacing.SM),
                    ft.Container(
                        content=self.list_container,
                        expand=True,
                    ),
                ],
                spacing=Spacing.MD,
                expand=True,
            ),
            padding=ft.padding.all(Spacing.XL),
            expand=True,
            bgcolor=Colors.BG_APP,
        )

    # -----------------------------------------------------------------------
    # Recarregar lista + resumo
    # -----------------------------------------------------------------------
    def _reload(self):
        today = date.today()
        with get_session() as s:
            # Item 4: só as contas que vencem no MÊS VIGENTE.
            all_bills = bill_service.list_bills(s, self.user.id, month=today)
            bills_data = [
                {
                    "id": b.id,
                    "description": b.description,
                    "amount": b.amount,
                    "due_date": b.due_date,
                    "is_paid": b.is_paid,
                    "paid_at": b.paid_at,
                    "is_recurring": b.is_recurring,
                }
                for b in all_bills
            ]

        # Calcula totais para o resumo
        total_pending = sum((b["amount"] for b in bills_data if not b["is_paid"]), Decimal("0"))
        total_paid = sum((b["amount"] for b in bills_data if b["is_paid"]), Decimal("0"))
        overdue = sum(
            (b["amount"] for b in bills_data
             if not b["is_paid"] and b["due_date"] < today),
            Decimal("0"),
        )

        # Atualiza o resumo (3 mini-cards)
        self.summary_row.controls = [
            self._summary_card("To pay", total_pending, Colors.TEXT_PRIMARY),
            self._summary_card("Overdues", overdue, Colors.DANGER),
            self._summary_card("Paid", total_paid, Colors.SUCCESS),
        ]

        # Reconstrói a lista
        self.list_container.controls.clear()
        if not bills_data:
            self.list_container.controls.append(
                ft.Container(
                    content=ft.Text("No bills yet. Click 'Add bill'.",
                                    color=Colors.TEXT_TERTIARY, size=Font.SIZE_BODY),
                    alignment=ft.alignment.center, padding=Spacing.XXL,
                )
            )
        else:
            for bd in bills_data:
                self.list_container.controls.append(self._bill_card(bd, today))

        if self.list_container.page is not None:
            self.summary_row.update()
            self.list_container.update()

    def _summary_card(self, label: str, amount: Decimal, color: str) -> ft.Control:
        return ft.Container(
            content=ft.Column(
                [
                    ft.Text(label, size=Font.SIZE_SMALL, color=Colors.TEXT_SECONDARY,
                            weight=Font.MEDIUM),
                    ft.Text(format_brl(amount), size=Font.SIZE_LARGE, weight=Font.BOLD,
                            color=color),
                ],
                spacing=Spacing.XS,
            ),
            bgcolor=Colors.BG_CARD,
            border=ft.border.all(1, Colors.BORDER),
            border_radius=Radius.LG,
            padding=Spacing.LG,
            expand=True,
        )

    def _bill_card(self, bd: dict, today: date) -> ft.Control:
        """Cada conta renderizada como um 'cartão de compra'."""
        is_paid = bd["is_paid"]
        is_overdue = (not is_paid) and bd["due_date"] < today

        # Status badge
        if is_paid:
            status_text, status_color, status_bg = "Paid", Colors.SUCCESS, "#E6F4EF"
        elif is_overdue:
            status_text, status_color, status_bg = "Overdue", Colors.DANGER, "#FBEAE5"
        else:
            status_text, status_color, status_bg = "Pending", "#B07A1E", "#FBF3E2"

        status_badge = ft.Container(
            content=ft.Text(status_text, size=Font.SIZE_TINY, color=status_color,
                            weight=Font.SEMIBOLD),
            bgcolor=status_bg,
            padding=ft.padding.symmetric(horizontal=Spacing.SM, vertical=2),
            border_radius=Radius.PILL,
        )

        # Selo de "recorrente" (assinatura) — aparece ao lado do status
        badges = [status_badge]
        if bd.get("is_recurring"):
            badges.append(
                ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.Icons.AUTORENEW, size=12, color=Colors.ACCENT),
                        ft.Text("Recurring", size=Font.SIZE_TINY, color=Colors.ACCENT,
                                weight=Font.SEMIBOLD),
                    ], spacing=2, tight=True),
                    bgcolor=Colors.ACCENT_SOFT,
                    padding=ft.padding.symmetric(horizontal=Spacing.SM, vertical=2),
                    border_radius=Radius.PILL,
                )
            )

        # Ações: marcar paga (se pendente) ou desmarcar (se paga) + duplicar + remover
        actions = []
        if not is_paid:
            actions.append(
                ft.IconButton(
                    icon=ft.Icons.CHECK_CIRCLE_OUTLINE,
                    icon_color=Colors.SUCCESS, icon_size=20,
                    tooltip="Mark as paid",
                    on_click=lambda e, bid=bd["id"]: self._open_pay_dialog(bid, bd["description"]),
                )
            )
        else:
            actions.append(
                ft.IconButton(
                    icon=ft.Icons.UNDO, icon_color=Colors.TEXT_TERTIARY, icon_size=20,
                    tooltip="Undo payment",
                    on_click=lambda e, bid=bd["id"]: self._unpay(bid),
                )
            )
        # Botão duplicar para o próximo mês (item 5)
        actions.append(
            ft.IconButton(
                icon=ft.Icons.COPY_ALL_OUTLINED, icon_color=Colors.TEXT_TERTIARY, icon_size=20,
                tooltip="Duplicate to next month",
                on_click=lambda e, bid=bd["id"]: self._duplicate(bid),
            )
        )
        actions.append(
            ft.IconButton(
                icon=ft.Icons.DELETE_OUTLINE, icon_color=Colors.TEXT_TERTIARY, icon_size=20,
                tooltip="Remove",
                on_click=lambda e, bid=bd["id"], desc=bd["description"]: self._confirm_delete(bid, desc),
            )
        )

        # Ícone à esquerda (como um "produto")
        leading_icon = ft.Container(
            content=ft.Icon(ft.Icons.RECEIPT_LONG_OUTLINED, color=Colors.ACCENT, size=22),
            width=44, height=44, bgcolor=Colors.ACCENT_SOFT,
            border_radius=Radius.MD, alignment=ft.alignment.center,
        )

        due_label = bd["due_date"].strftime("due on %m/%d/%Y")
        if is_paid and bd["paid_at"]:
            due_label = bd["paid_at"].strftime("paid on %m/%d/%Y")

        return ft.Container(
            content=ft.Row(
                [
                    leading_icon,
                    ft.Column(
                        [
                            ft.Row([
                                ft.Text(bd["description"], size=Font.SIZE_BODY,
                                        weight=Font.SEMIBOLD, color=Colors.TEXT_PRIMARY),
                                *badges,
                            ], spacing=Spacing.SM),
                            ft.Text(due_label, size=Font.SIZE_SMALL, color=Colors.TEXT_SECONDARY),
                        ],
                        spacing=2, expand=True,
                    ),
                    ft.Text(format_brl(bd["amount"]), size=Font.SIZE_LARGE,
                            weight=Font.BOLD, color=Colors.TEXT_PRIMARY),
                    ft.Row(actions, spacing=0, tight=True),
                ],
                spacing=Spacing.MD,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=Colors.BG_CARD,
            border=ft.border.all(1, Colors.BORDER),
            border_radius=Radius.LG,
            padding=Spacing.MD,
        )

    # -----------------------------------------------------------------------
    # Add conta
    # -----------------------------------------------------------------------
    def _open_add_dialog(self):
        desc_field = ft.TextField(label="Description (ex: Aluguel)", autofocus=True,
                                   border_color=Colors.BORDER, focused_border_color=Colors.ACCENT)
        amount_field = ft.TextField(label="Amount (e.g. 1450.00)", prefix_text="R$ ",
                                     border_color=Colors.BORDER, focused_border_color=Colors.ACCENT,
                                     keyboard_type=ft.KeyboardType.NUMBER)
        due_field = ft.TextField(label="Due date (dd/mm/yyyy)",
                                 value=date.today().strftime("%d/%m/%Y"),
                                 border_color=Colors.BORDER, focused_border_color=Colors.ACCENT)
        recurring_check = ft.Checkbox(
            label="Recurring subscription (regenerates next month when paid)",
            value=False,
            active_color=Colors.ACCENT,
        )
        error_text = ft.Text("", color=Colors.DANGER, size=Font.SIZE_SMALL, visible=False)

        def handle_save(e):
            desc = (desc_field.value or "").strip()
            if not desc:
                error_text.value = "Enter a description."
                error_text.visible = True
                error_text.update()
                return
            amount = self._parse_amount(amount_field.value)
            if amount is None:
                error_text.value = "Invalid amount."
                error_text.visible = True
                error_text.update()
                return
            try:
                due = datetime.strptime(due_field.value.strip(), "%d/%m/%Y").date()
            except ValueError:
                error_text.value = "Invalid date (use dd/mm/yyyy)."
                error_text.visible = True
                error_text.update()
                return

            with get_session() as s:
                bill_service.create_bill(
                    s, self.user.id, desc, amount, due,
                    is_recurring=bool(recurring_check.value),
                )

            self.page.close(dialog)
            self._reload()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("New bill", size=Font.SIZE_LARGE, weight=Font.BOLD),
            content=ft.Container(
                content=ft.Column([desc_field, amount_field, due_field,
                                   recurring_check, error_text],
                                  spacing=Spacing.MD, tight=True, width=380),
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

    # -----------------------------------------------------------------------
    # Paidr conta (com opção de registrar como transação)
    # -----------------------------------------------------------------------
    def _open_pay_dialog(self, bill_id: int, description: str):
        def handle_confirm(e):
            with get_session() as s:
                # Pagar sempre registra como gasto (mantém o "Available" estável)
                bill_service.mark_bill_paid(s, bill_id, self.user.id)
            self.page.close(dialog)
            self._reload()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Mark as paid", size=Font.SIZE_LARGE, weight=Font.BOLD),
            content=ft.Container(
                content=ft.Column(
                    [
                        ft.Text(f"Confirm payment of \"{description}\"?",
                                size=Font.SIZE_BODY, color=Colors.TEXT_PRIMARY),
                        ft.Text("It will be recorded as an expense in your history.",
                                size=Font.SIZE_SMALL, color=Colors.TEXT_SECONDARY),
                    ],
                    spacing=Spacing.SM, tight=True, width=380,
                ),
                padding=ft.padding.only(top=Spacing.SM),
            ),
            actions=[
                ft.TextButton(content=ft.Text("Cancel", color=Colors.TEXT_SECONDARY),
                              on_click=lambda e: self.page.close(dialog)),
                ft.TextButton(content=ft.Text("Confirm", color=Colors.SUCCESS, weight=Font.SEMIBOLD),
                              on_click=handle_confirm),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
            shape=ft.RoundedRectangleBorder(radius=Radius.LG),
        )
        self.page.open(dialog)

    def _unpay(self, bill_id: int):
        with get_session() as s:
            bill_service.mark_bill_unpaid(s, bill_id, self.user.id)
        self._reload()

    def _duplicate(self, bill_id: int):
        """Duplica a conta para o mês seguinte (item 5)."""
        with get_session() as s:
            nova = bill_service.duplicate_bill_to_next_month(s, bill_id, self.user.id)
        if nova is not None:
            self.page.open(ft.SnackBar(
                content=ft.Text("Bill duplicated to next month."),
                bgcolor=Colors.SUCCESS,
            ))
        # Nota: a cópia vai para o mês seguinte, então não aparece na
        # lista do mês atual (que mostra só o mês vigente). Ela aparecerá
        # quando você navegar/chegar ao próximo mês.
        self._reload()

    def _confirm_delete(self, bill_id: int, description: str):
        def do_delete():
            with get_session() as s:
                bill_service.delete_bill(s, bill_id, self.user.id)
            self._reload()

        confirm_dialog(
            self.page,
            title="Remove conta",
            message=f"Remove \"{description}\"?",
            on_confirm=do_delete,
            confirm_label="Remove",
            danger=True,
        )

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------
    def _parse_amount(self, raw: Optional[str]) -> Optional[Decimal]:
        if not raw:
            return None
        cleaned = raw.strip().replace(".", "").replace(",", ".")
        try:
            value = Decimal(cleaned)
            return value if value > 0 else None
        except (InvalidOperation, ValueError):
            return None
