"""
Tela de History (rota "transactions").

Funcionalidades:
  - Tabela de todas as transações
  - Busca por texto + filtros (tipo, categoria)
  - Botão "Import CSV" (abre seletor de arquivo)
  - Botão "Add" (formulário manual)
  - Remove transação (com confirmação)

NOTA SOBRE ESTADO:
Esta view tem ESTADO mutável (filtros atuais, lista carregada). Por
isso ela é uma CLASSE, não uma função — assim os métodos compartilham
o estado via self, e podemos recarregar a tabela quando algo muda.
"""

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Optional

import flet as ft

from app.database.connection import get_session
from app.database.models import Category, User
from app.services import category_service as cat_service
from app.services import transaction_service as tx_service
from app.services.csv_importer import import_csv_text
from app.ui.components.dialogs import confirm_dialog
from app.ui.theme import Colors, Font, Radius, Spacing, format_brl


class HistoryView:
    """View com estado para a tela de histórico."""

    def __init__(self, page: ft.Page, user: User):
        self.page = page
        self.user = user

        # Estado dos filtros
        self.filter_text: str = ""
        self.filter_kind: Optional[str] = None
        self.filter_category_id: Optional[int] = None

        # Carrega categorias uma vez (para os dropdowns)
        with get_session() as s:
            cats = s.query(Category).order_by(Category.name).all()
            for c in cats:
                s.expunge(c)
        self.categories = cats
        self.cat_name_by_id = {c.id: c.name for c in cats}

        # FilePicker precisa ser registrado na page para funcionar
        self.file_picker = ft.FilePicker(on_result=self._on_file_picked)
        self.page.overlay.append(self.file_picker)

        # Container da tabela — guardamos referência para atualizar depois
        self.table_container = ft.Column(spacing=0, scroll=ft.ScrollMode.AUTO, expand=True)

        # Texto de status (resultado de importação, contagem, etc.)
        self.status_text = ft.Text("", size=Font.SIZE_SMALL, color=Colors.TEXT_SECONDARY)

    # -----------------------------------------------------------------------
    # Construção da view
    # -----------------------------------------------------------------------
    def build(self) -> ft.Control:
        """Monta e retorna o controle raiz da tela."""
        header = self._build_header()
        filters = self._build_filters()

        self._reload_table()  # popula a tabela pela primeira vez

        return ft.Container(
            content=ft.Column(
                [
                    header,
                    ft.Container(height=Spacing.SM),
                    filters,
                    self.status_text,
                    ft.Container(
                        content=self.table_container,
                        expand=True,
                        bgcolor=Colors.BG_CARD,
                        border=ft.border.all(1, Colors.BORDER),
                        border_radius=Radius.LG,
                        padding=Spacing.LG,
                    ),
                ],
                spacing=Spacing.MD,
                expand=True,
            ),
            padding=ft.padding.all(Spacing.XL),
            expand=True,
            bgcolor=Colors.BG_APP,
        )

    def _build_header(self) -> ft.Control:
        """Título + botões de ação (Importar / Add)."""
        import_btn = ft.ElevatedButton(
            content=ft.Row(
                [ft.Icon(ft.Icons.UPLOAD_FILE_OUTLINED, size=18), ft.Text("Import CSV")],
                spacing=Spacing.SM, tight=True,
            ),
            on_click=lambda e: self.file_picker.pick_files(
                allowed_extensions=["csv"],
                dialog_title="Selecione o CSV do extrato",
            ),
            style=ft.ButtonStyle(
                bgcolor=Colors.BG_CARD,
                color=Colors.TEXT_PRIMARY,
                shape=ft.RoundedRectangleBorder(radius=Radius.MD),
                side=ft.BorderSide(1, Colors.BORDER),
            ),
            height=42,
        )

        add_btn = ft.ElevatedButton(
            content=ft.Row(
                [ft.Icon(ft.Icons.ADD, size=18), ft.Text("Add")],
                spacing=Spacing.SM, tight=True,
            ),
            on_click=lambda e: self._open_add_dialog(),
            style=ft.ButtonStyle(
                bgcolor=Colors.DARK,
                color=Colors.TEXT_ON_DARK,
                shape=ft.RoundedRectangleBorder(radius=Radius.MD),
            ),
            height=42,
        )

        return ft.Row(
            [
                ft.Text("History", size=Font.SIZE_TITLE, weight=Font.BOLD,
                        color=Colors.TEXT_PRIMARY),
                ft.Container(expand=True),
                import_btn,
                add_btn,
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=Spacing.SM,
        )

    def _build_filters(self) -> ft.Control:
        """Barra de busca + dropdowns de filtro."""
        search_field = ft.TextField(
            hint_text="Search by description...",
            prefix_icon=ft.Icons.SEARCH,
            on_change=self._on_search_change,
            border_color=Colors.BORDER,
            focused_border_color=Colors.ACCENT,
            height=44,
            expand=True,
            text_size=Font.SIZE_BODY,
            content_padding=ft.padding.symmetric(horizontal=Spacing.MD),
        )

        kind_dropdown = ft.Dropdown(
            hint_text="Type",
            options=[
                ft.dropdown.Option(key="", text="All types"),
                ft.dropdown.Option(key="expense", text="Expenses"),
                ft.dropdown.Option(key="income", text="Incomes"),
            ],
            on_change=self._on_kind_change,
            border_color=Colors.BORDER,
            width=170,
            text_size=Font.SIZE_BODY,
            content_padding=ft.padding.symmetric(horizontal=Spacing.MD),
        )

        category_options = [ft.dropdown.Option(key="", text="All categories")]
        for c in self.categories:
            category_options.append(ft.dropdown.Option(key=str(c.id), text=c.name))

        category_dropdown = ft.Dropdown(
            hint_text="Category",
            options=category_options,
            on_change=self._on_category_change,
            border_color=Colors.BORDER,
            width=200,
            text_size=Font.SIZE_BODY,
            content_padding=ft.padding.symmetric(horizontal=Spacing.MD),
        )

        return ft.Row(
            [search_field, kind_dropdown, category_dropdown],
            spacing=Spacing.MD,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

    # -----------------------------------------------------------------------
    # Tabela
    # -----------------------------------------------------------------------
    def _reload_table(self) -> None:
        """Recarrega a tabela com base nos filtros atuais."""
        # Limite de exibição: carregar e renderizar centenas de linhas de
        # uma vez deixa a tela lenta. Mostramos as mais recentes (a busca
        # e os filtros permitem achar transações específicas mais antigas).
        DISPLAY_LIMIT = 150
        with get_session() as s:
            results = tx_service.search_transactions(
                session=s,
                user_id=self.user.id,
                text=self.filter_text or None,
                kind=self.filter_kind,
                category_id=self.filter_category_id,
                limit=DISPLAY_LIMIT,
            )
            # Detacha para uso fora da sessão
            rows_data = [
                {
                    "id": t.id,
                    "date": t.occurred_at,
                    "description": t.description,
                    "amount": t.amount,
                    "kind": t.kind,
                    "category": self.cat_name_by_id.get(t.category_id, "—"),
                }
                for t in results
            ]

        if len(rows_data) >= DISPLAY_LIMIT:
            self.status_text.value = (
                f"Showing the {DISPLAY_LIMIT} most recent — use search or "
                f"filters to find older transactions"
            )
        else:
            self.status_text.value = f"{len(rows_data)} transaction(s) found"

        # Limpa e reconstrói as linhas
        self.table_container.controls.clear()
        self.table_container.controls.append(self._table_header())
        for rd in rows_data:
            self.table_container.controls.append(self._table_row(rd))

        # Atualiza só se já estiver na página (evita erro na 1ª construção)
        if self.table_container.page is not None:
            self.table_container.update()
            self.status_text.update()

    def _table_header(self) -> ft.Control:
        def h(text, expand, right=False):
            return ft.Container(
                content=ft.Text(text, size=Font.SIZE_SMALL, weight=Font.MEDIUM,
                                color=Colors.TEXT_TERTIARY),
                expand=expand,
                alignment=ft.alignment.center_right if right else ft.alignment.center_left,
            )

        return ft.Container(
            content=ft.Row([
                h("Date", 2),
                h("Description", 5),
                h("Category", 2),
                h("Amount", 2, right=True),
                h("", 1, right=True),  # coluna do botão de deletar
            ]),
            padding=ft.padding.only(bottom=Spacing.SM),
            border=ft.border.only(bottom=ft.BorderSide(1, Colors.BORDER)),
        )

    def _table_row(self, rd: dict) -> ft.Control:
        is_expense = rd["kind"] == "expense"
        # Expenses em preto, entradas em verde com prefixo +
        amount_color = Colors.TEXT_PRIMARY if is_expense else Colors.SUCCESS
        amount_prefix = "" if is_expense else "+"

        def cell(text, expand, color=Colors.TEXT_PRIMARY, right=False, weight=Font.REGULAR):
            return ft.Container(
                content=ft.Text(text, size=Font.SIZE_BODY, color=color, weight=weight,
                                no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS),
                expand=expand,
                alignment=ft.alignment.center_right if right else ft.alignment.center_left,
            )

        edit_btn = ft.IconButton(
            icon=ft.Icons.EDIT_OUTLINED,
            icon_color=Colors.TEXT_TERTIARY,
            icon_size=18,
            tooltip="Edit",
            on_click=lambda e, r=rd: self._open_edit_dialog(r),
        )

        delete_btn = ft.IconButton(
            icon=ft.Icons.DELETE_OUTLINE,
            icon_color=Colors.TEXT_TERTIARY,
            icon_size=18,
            tooltip="Delete",
            on_click=lambda e, tid=rd["id"], desc=rd["description"]: self._confirm_delete(tid, desc),
        )

        return ft.Container(
            content=ft.Row([
                cell(rd["date"].strftime("%m/%d/%Y"), 2, color=Colors.TEXT_SECONDARY),
                cell(rd["description"], 5),
                cell(rd["category"], 2, color=Colors.TEXT_SECONDARY),
                cell(f"{amount_prefix}{format_brl(rd['amount'])}", 2, color=amount_color,
                     right=True, weight=Font.MEDIUM),
                ft.Container(content=ft.Row([edit_btn, delete_btn], spacing=0, tight=True),
                             expand=2, alignment=ft.alignment.center_right),
            ]),
            padding=ft.padding.symmetric(vertical=Spacing.XS),
            border=ft.border.only(bottom=ft.BorderSide(1, Colors.DIVIDER)),
        )

    # -----------------------------------------------------------------------
    # Handlers de filtro
    # -----------------------------------------------------------------------
    def _on_search_change(self, e):
        self.filter_text = e.control.value
        self._reload_table()

    def _on_kind_change(self, e):
        self.filter_kind = e.control.value or None
        self._reload_table()

    def _on_category_change(self, e):
        val = e.control.value
        self.filter_category_id = int(val) if val else None
        self._reload_table()

    # -----------------------------------------------------------------------
    # Importação de CSV
    # -----------------------------------------------------------------------
    def _on_file_picked(self, e: ft.FilePickerResultEvent):
        """Callback do FilePicker quando o usuário escolhe um arquivo."""
        if not e.files:
            return  # cancelou

        file = e.files[0]
        # No desktop, file.path tem o caminho local. Lemos o conteúdo.
        try:
            with open(file.path, "r", encoding="utf-8") as f:
                text = f.read()
        except Exception as ex:
            self.status_text.value = f"Erro ao ler arquivo: {ex}"
            self.status_text.color = Colors.DANGER
            self.status_text.update()
            return

        with get_session() as s:
            result = import_csv_text(s, self.user.id, text)

        self.status_text.value = f"Import complete: {result.summary()}"
        self.status_text.color = Colors.SUCCESS if result.imported else Colors.TEXT_SECONDARY
        self.status_text.update()
        self._reload_table()

    # -----------------------------------------------------------------------
    # Add transação manual
    # -----------------------------------------------------------------------
    def _open_add_dialog(self):
        """Abre um diálogo com formulário de nova transação."""
        desc_field = ft.TextField(label="Description", autofocus=True,
                                   border_color=Colors.BORDER, focused_border_color=Colors.ACCENT)
        amount_field = ft.TextField(label="Amount (e.g. 49.90)", prefix_text="R$ ",
                                     border_color=Colors.BORDER, focused_border_color=Colors.ACCENT,
                                     keyboard_type=ft.KeyboardType.NUMBER)
        date_field = ft.TextField(label="Date (mm/dd/yyyy)",
                                   value=date.today().strftime("%d/%m/%Y"),
                                   border_color=Colors.BORDER, focused_border_color=Colors.ACCENT)
        kind_dropdown = ft.Dropdown(
            label="Type",
            value="expense",
            options=[
                ft.dropdown.Option(key="expense", text="Expense"),
                ft.dropdown.Option(key="income", text="Income"),
            ],
            border_color=Colors.BORDER,
        )
        category_dropdown = ft.Dropdown(
            label="Category",
            options=[ft.dropdown.Option(key="", text="(no category)")] +
                    [ft.dropdown.Option(key=str(c.id), text=c.name) for c in self.categories],
            border_color=Colors.BORDER,
        )
        error_text = ft.Text("", color=Colors.DANGER, size=Font.SIZE_SMALL, visible=False)

        def handle_save(e):
            # Validação dos campos
            desc = (desc_field.value or "").strip()
            if not desc:
                return self._show_form_error(error_text, "Enter a description.")

            amount = self._parse_amount(amount_field.value)
            if amount is None:
                return self._show_form_error(error_text, "Invalid amount.")

            try:
                occurred = datetime.strptime(date_field.value.strip(), "%d/%m/%Y").date()
            except ValueError:
                return self._show_form_error(error_text, "Invalid date (use mm/dd/yyyy).")

            cat_id = int(category_dropdown.value) if category_dropdown.value else None

            with get_session() as s:
                tx_service.create_transaction(
                    session=s, user_id=self.user.id,
                    description=desc, amount=amount,
                    kind=kind_dropdown.value, occurred_at=occurred,
                    category_id=cat_id,
                )

            self.page.close(dialog)
            self._reload_table()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("New transaction", size=Font.SIZE_LARGE, weight=Font.BOLD),
            content=ft.Container(
                content=ft.Column(
                    [desc_field, amount_field, date_field, kind_dropdown,
                     category_dropdown, error_text],
                    spacing=Spacing.MD, tight=True, width=380,
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

    # -----------------------------------------------------------------------
    # Editar transação (categoria) com opção de tornar padrão
    # -----------------------------------------------------------------------
    def _open_edit_dialog(self, rd: dict):
        """
        Edita a categoria de uma transação. Com o checkbox marcado,
        aplica a todas as transações com a mesma descrição E cria uma
        regra para categorizar as próximas automaticamente.
        """
        # Dropdown de categorias (inclui "no category")
        cat_options = [ft.dropdown.Option(key="", text="(no category)")]
        for c in self.categories:
            cat_options.append(ft.dropdown.Option(key=str(c.id), text=c.name))

        # Pré-seleciona a categoria atual da transação
        current_cat_id = None
        for c in self.categories:
            if c.name == rd["category"]:
                current_cat_id = c.id
                break

        cat_dropdown = ft.Dropdown(
            label="Category",
            options=cat_options,
            value=str(current_cat_id) if current_cat_id else "",
            border_color=Colors.BORDER,
        )

        make_default = ft.Checkbox(
            label="Apply to all with this description and remember for next time",
            value=True,
            active_color=Colors.ACCENT,
        )

        def handle_save(e):
            new_cat_id = int(cat_dropdown.value) if cat_dropdown.value else None

            with get_session() as s:
                if make_default.value:
                    # Aplica a todas as parecidas
                    tx_service.recategorize_similar(
                        s, self.user.id, rd["description"], new_cat_id
                    )
                    # Cria uma regra para as próximas (se escolheu uma categoria)
                    if new_cat_id is not None:
                        # Evita duplicar regra idêntica
                        existing = [
                            r for r in cat_service.list_rules(s, self.user.id)
                            if r.pattern.upper() == rd["description"].strip().upper()
                        ]
                        if not existing:
                            cat_service.create_rule(
                                s, self.user.id, rd["description"].strip(), new_cat_id
                            )
                else:
                    # Só esta transação
                    tx_service.update_transaction(
                        s, rd["id"], self.user.id, category_id=new_cat_id
                    )

            self.page.close(dialog)
            self._reload_table()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Edit category", size=Font.SIZE_LARGE, weight=Font.BOLD),
            content=ft.Container(
                content=ft.Column([
                    ft.Text(f"\"{rd['description']}\"", size=Font.SIZE_BODY,
                            weight=Font.MEDIUM, color=Colors.TEXT_PRIMARY),
                    cat_dropdown,
                    make_default,
                ], spacing=Spacing.MD, tight=True, width=400),
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
    # Remove transação
    # -----------------------------------------------------------------------
    def _confirm_delete(self, transaction_id: int, description: str):
        def do_delete():
            with get_session() as s:
                tx_service.delete_transaction(s, transaction_id, self.user.id)
            self._reload_table()

        confirm_dialog(
            self.page,
            title="Remove transaction",
            message=f"Remove \"{description}\"? This action cannot be undone.",
            on_confirm=do_delete,
            confirm_label="Remove",
            danger=True,
        )

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------
    def _parse_amount(self, raw: Optional[str]) -> Optional[Decimal]:
        """Converte '49,90' ou '49.90' em Decimal. Retorna None se inválido."""
        if not raw:
            return None
        # Aceita vírgula (BR) ou ponto como separador decimal
        cleaned = raw.strip().replace(".", "").replace(",", ".")
        try:
            value = Decimal(cleaned)
            return value if value > 0 else None
        except (InvalidOperation, ValueError):
            return None

    def _show_form_error(self, error_text: ft.Text, message: str):
        error_text.value = message
        error_text.visible = True
        error_text.update()
