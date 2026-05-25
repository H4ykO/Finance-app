"""
Tela de cadastro inicial (primeira abertura do app).

Aparece UMA vez, quando o banco ainda não tem nenhum usuário — em vez
de pedir para rodar o script init_db no terminal (que não existe no
.app empacotado). Cria a conta (admin) e entra direto no app.

Mesmo estilo visual da tela de login.
"""

from typing import Callable

import flet as ft

from app.database.connection import get_session
from app.database.models import User
from app.services.user_service import UserAlreadyExistsError, create_user
from app.ui.theme import Colors, Font, Radius, Spacing


def build_signup_view(
    page: ft.Page,
    on_signup_success: Callable[[User], None],
) -> ft.Control:
    """
    Constrói a tela de cadastro inicial.

    `on_signup_success` é chamado com o usuário recém-criado, para o
    controller entrar no app já logado.
    """

    name_field = ft.TextField(
        label="Your name",
        prefix_icon=ft.Icons.PERSON_OUTLINE,
        autofocus=True,
        border_color=Colors.BORDER,
        focused_border_color=Colors.ACCENT,
        text_size=Font.SIZE_BODY,
        height=52,
    )

    email_field = ft.TextField(
        label="E-mail",
        hint_text="you@email.com",
        prefix_icon=ft.Icons.EMAIL_OUTLINED,
        keyboard_type=ft.KeyboardType.EMAIL,
        border_color=Colors.BORDER,
        focused_border_color=Colors.ACCENT,
        text_size=Font.SIZE_BODY,
        height=52,
    )

    password_field = ft.TextField(
        label="Password",
        prefix_icon=ft.Icons.LOCK_OUTLINE,
        password=True,
        can_reveal_password=True,
        border_color=Colors.BORDER,
        focused_border_color=Colors.ACCENT,
        text_size=Font.SIZE_BODY,
        height=52,
    )

    confirm_field = ft.TextField(
        label="Confirm password",
        prefix_icon=ft.Icons.LOCK_OUTLINE,
        password=True,
        can_reveal_password=True,
        border_color=Colors.BORDER,
        focused_border_color=Colors.ACCENT,
        text_size=Font.SIZE_BODY,
        height=52,
    )

    error_text = ft.Text("", color=Colors.DANGER, size=Font.SIZE_SMALL, visible=False)

    def show_error(msg: str):
        error_text.value = msg
        error_text.visible = True
        error_text.update()

    def handle_signup(e):
        name = (name_field.value or "").strip()
        email = (email_field.value or "").strip().lower()
        password = password_field.value or ""
        confirm = confirm_field.value or ""

        # Validações
        if not name:
            show_error("Please enter your name.")
            return
        if not email or "@" not in email:
            show_error("Please enter a valid e-mail.")
            return
        if len(password) < 6:
            show_error("Password must be at least 6 characters.")
            return
        if password != confirm:
            show_error("Passwords do not match.")
            return

        # Cria o usuário (o primeiro é admin)
        try:
            with get_session() as session:
                user = create_user(
                    session=session,
                    email=email,
                    password=password,
                    name=name,
                    is_admin=True,
                )
                # Desacopla da sessão para usar fora dela
                session.expunge(user)
        except UserAlreadyExistsError:
            show_error("An account with this e-mail already exists.")
            return

        on_signup_success(user)

    # Enter no último campo confirma
    confirm_field.on_submit = handle_signup

    signup_button = ft.ElevatedButton(
        text="Create account",
        on_click=handle_signup,
        style=ft.ButtonStyle(
            bgcolor=Colors.ACCENT,
            color=Colors.TEXT_ON_DARK,
            shape=ft.RoundedRectangleBorder(radius=Radius.MD),
            padding=ft.padding.symmetric(vertical=Spacing.MD),
            text_style=ft.TextStyle(size=Font.SIZE_BODY, weight=Font.SEMIBOLD),
        ),
        width=400,
        height=52,
    )

    card = ft.Container(
        content=ft.Column(
            [
                ft.Icon(ft.Icons.ACCOUNT_BALANCE_WALLET, size=48, color=Colors.ACCENT),
                ft.Container(height=Spacing.SM),
                ft.Text("Welcome!", size=Font.SIZE_TITLE, weight=Font.BOLD,
                        color=Colors.TEXT_PRIMARY),
                ft.Text("Create your account to get started",
                        size=Font.SIZE_BODY, color=Colors.TEXT_SECONDARY),
                ft.Container(height=Spacing.LG),
                name_field,
                email_field,
                password_field,
                confirm_field,
                error_text,
                ft.Container(height=Spacing.SM),
                signup_button,
            ],
            spacing=Spacing.MD,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            tight=True,
        ),
        width=460,
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
