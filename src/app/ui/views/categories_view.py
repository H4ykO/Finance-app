"""
Tela de Categorys (rota "categories").

Duas seções:
  1. Categorys — lista com criar/editar/remover
  2. Categorization rules — "se descrição contém X, categoria Y"

Como tem estado mutável (recarregar listas após mudanças), é uma classe.
"""

from typing import Optional

import flet as ft

from app.database.connection import get_session
from app.database.models import User
from app.services import category_service as cs
from app.ui.components.dialogs import confirm_dialog
from app.ui.theme import Colors, Font, Radius, Spacing


# Paleta de cores sugeridas para novas categorias (da identidade do app)
SUGGESTED_COLORS = [
    "#E85D24", "#1D9E75", "#7F77DD", "#F2A623",
    "#D4537E", "#378ADD", "#534AB7", "#888780",
]


class CategoriesView:
    def __init__(self, page: ft.Page, user: User):
        self.page = page
        self.user = user
        self.cats_container = ft.Column(spacing=Spacing.SM)
        self.rules_container = ft.Column(spacing=Spacing.SM)

    def build(self) -> ft.Control:
        header = ft.Text("Categorys", size=Font.SIZE_TITLE, weight=Font.BOLD,
                         color=Colors.TEXT_PRIMARY)

        # Seção categorias
        cats_section = ft.Container(
            content=ft.Column(
                [
                    ft.Row([
                        ft.Text("Your categories", size=Font.SIZE_LARGE, weight=Font.SEMIBOLD,
                                color=Colors.TEXT_PRIMARY),
                        ft.Container(expand=True),
                        ft.ElevatedButton(
                            content=ft.Row([ft.Icon(ft.Icons.ADD, size=16), ft.Text("New")],
                                           spacing=4, tight=True),
                            on_click=lambda e: self._open_category_dialog(),
                            style=ft.ButtonStyle(bgcolor=Colors.DARK, color=Colors.TEXT_ON_DARK,
                                                 shape=ft.RoundedRectangleBorder(radius=Radius.MD)),
                            height=38,
                        ),
                    ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    self.cats_container,
                ],
                spacing=Spacing.MD,
            ),
            bgcolor=Colors.BG_CARD, border=ft.border.all(1, Colors.BORDER),
            border_radius=Radius.LG, padding=Spacing.LG,
        )

        # Seção regras
        rules_section = ft.Container(
            content=ft.Column(
                [
                    ft.Row([
                        ft.Column([
                            ft.Text("Categorization rules", size=Font.SIZE_LARGE,
                                    weight=Font.SEMIBOLD, color=Colors.TEXT_PRIMARY),
                            ft.Text("If the description contains... texto, aplica a categoria.",
                                    size=Font.SIZE_SMALL, color=Colors.TEXT_SECONDARY),
                        ], spacing=0, expand=True),
                        ft.ElevatedButton(
                            content=ft.Row([ft.Icon(ft.Icons.ADD, size=16), ft.Text("New rule")],
                                           spacing=4, tight=True),
                            on_click=lambda e: self._open_rule_dialog(),
                            style=ft.ButtonStyle(bgcolor=Colors.DARK, color=Colors.TEXT_ON_DARK,
                                                 shape=ft.RoundedRectangleBorder(radius=Radius.MD)),
                            height=38,
                        ),
                    ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    self.rules_container,
                ],
                spacing=Spacing.MD,
            ),
            bgcolor=Colors.BG_CARD, border=ft.border.all(1, Colors.BORDER),
            border_radius=Radius.LG, padding=Spacing.LG,
        )

        self._reload_categories()
        self._reload_rules()

        return ft.Container(
            content=ft.Column(
                [header, ft.Container(height=Spacing.SM), cats_section, rules_section],
                spacing=Spacing.MD, scroll=ft.ScrollMode.AUTO, expand=True,
            ),
            padding=ft.padding.all(Spacing.XL), expand=True, bgcolor=Colors.BG_APP,
        )

    # -----------------------------------------------------------------------
    # Categorys
    # -----------------------------------------------------------------------
    def _reload_categories(self):
        with get_session() as s:
            cats = cs.list_categories(s)
            data = [(c.id, c.name, c.color, c.icon) for c in cats]

        self.cats_container.controls.clear()
        for cid, name, color, icon in data:
            self.cats_container.controls.append(self._category_row(cid, name, color, icon))
        if self.cats_container.page is not None:
            self.cats_container.update()

    def _category_row(self, cid: int, name: str, color: str, icon: str) -> ft.Control:
        color_dot = ft.Container(width=18, height=18, bgcolor=color, border_radius=Radius.PILL)
        is_outros = name == cs.FALLBACK_CATEGORY_NAME

        actions = [
            ft.IconButton(icon=ft.Icons.EDIT_OUTLINED, icon_size=18, icon_color=Colors.TEXT_TERTIARY,
                          tooltip="Editar",
                          on_click=lambda e, i=cid, n=name, c=color, ic=icon: self._open_category_dialog(i, n, c, ic)),
        ]
        # Não permite remover "Outros"
        if not is_outros:
            actions.append(
                ft.IconButton(icon=ft.Icons.DELETE_OUTLINE, icon_size=18, icon_color=Colors.TEXT_TERTIARY,
                              tooltip="Remove",
                              on_click=lambda e, i=cid, n=name: self._confirm_delete_category(i, n))
            )

        return ft.Container(
            content=ft.Row([
                color_dot,
                ft.Text(name, size=Font.SIZE_BODY, color=Colors.TEXT_PRIMARY, expand=True),
                ft.Row(actions, spacing=0, tight=True),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=Spacing.MD),
            padding=ft.padding.symmetric(vertical=Spacing.XS),
            border=ft.border.only(bottom=ft.BorderSide(1, Colors.DIVIDER)),
        )

    def _open_category_dialog(self, cid: Optional[int] = None, name: str = "",
                              color: str = SUGGESTED_COLORS[0], icon: str = "category"):
        is_edit = cid is not None
        name_field = ft.TextField(label="Nome", value=name, autofocus=True,
                                  border_color=Colors.BORDER, focused_border_color=Colors.ACCENT)
        error_text = ft.Text("", color=Colors.DANGER, size=Font.SIZE_SMALL, visible=False)

        # Seletor de cor simples: linha de bolinhas clicáveis
        selected_color = {"value": color}
        color_dots_row = ft.Row(spacing=Spacing.SM)

        def make_dot(c):
            def pick(e):
                selected_color["value"] = c
                rebuild_dots()
            border = ft.border.all(2, Colors.TEXT_PRIMARY) if c == selected_color["value"] else None
            return ft.Container(width=28, height=28, bgcolor=c, border_radius=Radius.PILL,
                                border=border, on_click=pick, ink=True)

        def rebuild_dots():
            color_dots_row.controls = [make_dot(c) for c in SUGGESTED_COLORS]
            if color_dots_row.page is not None:
                color_dots_row.update()

        rebuild_dots()

        def handle_save(e):
            try:
                with get_session() as s:
                    if is_edit:
                        cs.update_category(s, cid, name=name_field.value, color=selected_color["value"])
                    else:
                        cs.create_category(s, name_field.value, color=selected_color["value"])
            except ValueError as ex:
                error_text.value = str(ex)
                error_text.visible = True
                error_text.update()
                return
            self.page.close(dialog)
            self._reload_categories()
            self._reload_rules()  # nomes de categoria podem ter mudado

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Edit category" if is_edit else "New category",
                          size=Font.SIZE_LARGE, weight=Font.BOLD),
            content=ft.Container(
                content=ft.Column([
                    name_field,
                    ft.Text("Color", size=Font.SIZE_SMALL, color=Colors.TEXT_SECONDARY),
                    color_dots_row,
                    error_text,
                ], spacing=Spacing.MD, tight=True, width=380),
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

    def _confirm_delete_category(self, cid: int, name: str):
        def do_delete():
            try:
                with get_session() as s:
                    ok, moved = cs.delete_category(s, cid)
            except ValueError:
                return
            self._reload_categories()
            self._reload_rules()

        confirm_dialog(
            self.page, title="Remove category",
            message=f"Remove \"{name}\"? Its transactions will move to \"Other\".",
            on_confirm=do_delete, confirm_label="Remove", danger=True,
        )

    # -----------------------------------------------------------------------
    # Regras
    # -----------------------------------------------------------------------
    def _reload_rules(self):
        with get_session() as s:
            rules = cs.list_rules(s, self.user.id)
            data = [(r.id, r.pattern, r.category.name if r.category else "—") for r in rules]

        self.rules_container.controls.clear()
        if not data:
            self.rules_container.controls.append(
                ft.Text("No rules yet. Edit a transaction in History and check 'remember for next time' to create one.",
                        size=Font.SIZE_SMALL, color=Colors.TEXT_TERTIARY)
            )
        else:
            for rid, pattern, cat_name in data:
                self.rules_container.controls.append(self._rule_row(rid, pattern, cat_name))
        if self.rules_container.page is not None:
            self.rules_container.update()

    def _rule_row(self, rid: int, pattern: str, cat_name: str) -> ft.Control:
        return ft.Container(
            content=ft.Row([
                ft.Text(f"\"{pattern}\"", size=Font.SIZE_BODY, color=Colors.TEXT_PRIMARY,
                        weight=Font.MEDIUM),
                ft.Icon(ft.Icons.ARROW_FORWARD, size=16, color=Colors.TEXT_TERTIARY),
                ft.Text(cat_name, size=Font.SIZE_BODY, color=Colors.TEXT_SECONDARY, expand=True),
                ft.IconButton(icon=ft.Icons.DELETE_OUTLINE, icon_size=18,
                              icon_color=Colors.TEXT_TERTIARY, tooltip="Remove",
                              on_click=lambda e, i=rid: self._delete_rule(i)),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=Spacing.SM),
            padding=ft.padding.symmetric(vertical=Spacing.XS),
            border=ft.border.only(bottom=ft.BorderSide(1, Colors.DIVIDER)),
        )

    def _open_rule_dialog(self):
        with get_session() as s:
            cats = cs.list_categories(s)
            cat_options = [(c.id, c.name) for c in cats]

        pattern_field = ft.TextField(label="If the description contains...", autofocus=True,
                                     hint_text="ex: EMPORIO DAMHA",
                                     border_color=Colors.BORDER, focused_border_color=Colors.ACCENT)
        cat_dropdown = ft.Dropdown(
            label="Category",
            options=[ft.dropdown.Option(key=str(cid), text=name) for cid, name in cat_options],
            value=str(cat_options[0][0]) if cat_options else None,
            border_color=Colors.BORDER,
        )
        error_text = ft.Text("", color=Colors.DANGER, size=Font.SIZE_SMALL, visible=False)

        def handle_save(e):
            pattern = (pattern_field.value or "").strip()
            if not pattern:
                error_text.value = "Enter the text to search for."
                error_text.visible = True
                error_text.update()
                return
            if not cat_dropdown.value:
                error_text.value = "Choose a category."
                error_text.visible = True
                error_text.update()
                return
            with get_session() as s:
                cs.create_rule(s, self.user.id, pattern, int(cat_dropdown.value))
            self.page.close(dialog)
            self._reload_rules()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("New rule", size=Font.SIZE_LARGE, weight=Font.BOLD),
            content=ft.Container(
                content=ft.Column([
                    ft.Text("When a transaction description contains the text below, "
                            "it will get the chosen category.",
                            size=Font.SIZE_SMALL, color=Colors.TEXT_SECONDARY),
                    pattern_field, cat_dropdown, error_text,
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

    def _delete_rule(self, rid: int):
        with get_session() as s:
            cs.delete_rule(s, rid, self.user.id)
        self._reload_rules()
