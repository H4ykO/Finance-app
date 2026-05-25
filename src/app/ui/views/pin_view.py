"""
Tela de acesso rápido por PIN.

Mostrada quando o usuário já fez login completo nesta sessão de boot
(o PC não reiniciou). Pede apenas um PIN curto em vez da senha completa.
Há um atalho para usar a senha (ex: se esqueceu o PIN), que leva de
volta ao login completo.
"""

from typing import Callable

import flet as ft

from app.database.connection import get_session
from app.services import user_service
from app.ui.theme import Colors, Font, Radius, Spacing


def build_pin_view(
    page: ft.Page,
    on_pin_success: Callable[[], None],
    on_use_password: Callable[[], None],
) -> ft.Control:
    """
    Constrói a tela de PIN.

    `on_pin_success` é chamado quando o PIN está correto.
    `on_use_password` leva ao login completo (e-mail + senha).
    """

    pin_field = ft.TextField(
        label="Enter your PIN",
        password=True,
        can_reveal_password=True,
        autofocus=True,
        keyboard_type=ft.KeyboardType.NUMBER,
        text_align=ft.TextAlign.CENTER,
        border_color=Colors.BORDER,
        focused_border_color=Colors.ACCENT,
        text_size=Font.SIZE_LARGE,
        height=56,
    )
    error_text = ft.Text("", color=Colors.DANGER, size=Font.SIZE_SMALL, visible=False)

    def handle_submit(e):
        pin = (pin_field.value or "").strip()
        if not pin:
            return
        with get_session() as s:
            user = user_service.get_single_user(s)
            ok = user_service.verify_user_pin(s, user.id, pin) if user else False
        if ok:
            on_pin_success()
        else:
            error_text.value = "Incorrect PIN. Try again or use your password."
            error_text.visible = True
            pin_field.value = ""
            pin_field.update()
            error_text.update()

    pin_field.on_submit = handle_submit

    unlock_button = ft.ElevatedButton(
        text="Unlock",
        on_click=handle_submit,
        style=ft.ButtonStyle(
            bgcolor=Colors.ACCENT,
            color=Colors.TEXT_ON_DARK,
            shape=ft.RoundedRectangleBorder(radius=Radius.MD),
            padding=ft.padding.symmetric(vertical=Spacing.MD),
            text_style=ft.TextStyle(size=Font.SIZE_BODY, weight=Font.SEMIBOLD),
        ),
        width=360, height=52,
    )

    use_password = ft.TextButton(
        content=ft.Text("Use password instead", color=Colors.TEXT_SECONDARY,
                        size=Font.SIZE_SMALL),
        on_click=lambda e: on_use_password(),
    )

    card = ft.Container(
        content=ft.Column(
            [
                ft.Icon(ft.Icons.LOCK_OUTLINE, size=44, color=Colors.ACCENT),
                ft.Container(height=Spacing.SM),
                ft.Text("Welcome back", size=Font.SIZE_TITLE, weight=Font.BOLD,
                        color=Colors.TEXT_PRIMARY),
                ft.Text("Enter your PIN to continue", size=Font.SIZE_BODY,
                        color=Colors.TEXT_SECONDARY),
                ft.Container(height=Spacing.LG),
                pin_field,
                error_text,
                ft.Container(height=Spacing.SM),
                unlock_button,
                use_password,
            ],
            spacing=Spacing.MD,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            tight=True,
        ),
        width=420,
        padding=Spacing.XL,
        bgcolor=Colors.BG_CARD,
        border=ft.border.all(1, Colors.BORDER),
        border_radius=Radius.LG,
    )

    return ft.Container(
        content=card,
        alignment=ft.alignment.center,
        expand=True,
        bgcolor=Colors.BG_APP,
    )
