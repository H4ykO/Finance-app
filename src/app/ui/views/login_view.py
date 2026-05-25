"""
Tela de login.

Layout: card centralizado com logo, título, dois campos e um botão.
Estilo consistente com o restante do app (paleta do tema).
"""

from typing import Callable

import flet as ft

from app.database.connection import get_session
from app.database.models import User
from app.services.user_service import InvalidCredentialsError, authenticate
from app.ui.theme import Colors, Font, Radius, Spacing


def build_login_view(
    page: ft.Page,
    on_login_success: Callable[[User], None],
) -> ft.Control:
    """
    Constrói a tela de login.

    `on_login_success` é o callback do controller para trocar de view
    após o login OK. Mantém o componente desacoplado do roteador.
    """

    # Campos de entrada
    email_field = ft.TextField(
        label="E-mail",
        hint_text="you@email.com",
        prefix_icon=ft.Icons.EMAIL_OUTLINED,
        autofocus=True,
        keyboard_type=ft.KeyboardType.EMAIL,
        # Estilo "outlined" — borda visível, sem fundo preenchido
        border_color=Colors.BORDER,
        focused_border_color=Colors.ACCENT,
        text_size=Font.SIZE_BODY,
        height=52,
    )

    password_field = ft.TextField(
        label="Password",
        prefix_icon=ft.Icons.LOCK_OUTLINE,
        password=True,           # esconde os caracteres
        can_reveal_password=True, # botão de mostrar/esconder
        border_color=Colors.BORDER,
        focused_border_color=Colors.ACCENT,
        text_size=Font.SIZE_BODY,
        height=52,
    )

    # Texto para erros — fica vazio por padrão e aparece quando login falha
    error_text = ft.Text(
        "",
        color=Colors.DANGER,
        size=Font.SIZE_SMALL,
        visible=False,
    )

    # Handler do botão de login
    def handle_login(e):
        # Limpa erro anterior
        error_text.visible = False
        page.update()

        email = (email_field.value or "").strip()
        password = password_field.value or ""

        if not email or not password:
            error_text.value = "Enter email and password."
            error_text.visible = True
            page.update()
            return

        # Autentica contra o banco
        with get_session() as session:
            try:
                user = authenticate(session, email, password)
            except InvalidCredentialsError:
                # Mensagem genérica de propósito — não diz se é o e-mail
                # ou a senha que está errado (segurança)
                error_text.value = "Incorrect email or password."
                error_text.visible = True
                page.update()
                return

            # Importante: chamamos session.expunge para que o objeto user
            # continue utilizável FORA do bloco `with` (a sessão será fechada)
            session.expunge(user)

        # Login OK — limpa campos e dispara o callback
        password_field.value = ""
        on_login_success(user)

    # Permite logar apertando Enter no campo de senha
    password_field.on_submit = handle_login

    # Logo grande no topo do card (dois círculos sobrepostos)
    logo = ft.Stack(
        [
            ft.Container(
                width=48, height=48,
                bgcolor=Colors.ACCENT,
                border_radius=Radius.PILL,
            ),
            ft.Container(
                width=30, height=30,
                bgcolor="#5DCAA5",
                border_radius=Radius.PILL,
                left=26, top=22,
            ),
        ],
        width=64, height=56,
    )

    # Card central com tudo dentro
    login_card = ft.Container(
        content=ft.Column(
            [
                ft.Container(content=logo, alignment=ft.alignment.center),
                ft.Container(height=Spacing.MD),
                ft.Text(
                    "Welcome back",
                    size=Font.SIZE_TITLE,
                    weight=Font.BOLD,
                    color=Colors.TEXT_PRIMARY,
                    text_align=ft.TextAlign.CENTER,
                ),
                ft.Text(
                    "Sign in to access the app",
                    size=Font.SIZE_BODY,
                    color=Colors.TEXT_SECONDARY,
                    text_align=ft.TextAlign.CENTER,
                ),
                ft.Container(height=Spacing.LG),
                email_field,
                password_field,
                ft.Container(content=error_text, padding=ft.padding.symmetric(vertical=Spacing.XS)),
                ft.Container(height=Spacing.SM),
                # Botão primário escuro (estilo do botão "Share" do dashboard)
                ft.ElevatedButton(
                    text="Sign in",
                    on_click=handle_login,
                    width=float("inf"),
                    height=52,
                    style=ft.ButtonStyle(
                        bgcolor=Colors.DARK,
                        color=Colors.TEXT_ON_DARK,
                        shape=ft.RoundedRectangleBorder(radius=Radius.MD),
                        text_style=ft.TextStyle(
                            size=Font.SIZE_BODY,
                            weight=Font.SEMIBOLD,
                        ),
                    ),
                ),
            ],
            spacing=Spacing.SM,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        ),
        width=420,
        padding=Spacing.XL,
        bgcolor=Colors.BG_CARD,
        border=ft.border.all(1, Colors.BORDER),
        border_radius=Radius.XL,
    )

    # Container raiz: ocupa a tela inteira e centraliza o card
    return ft.Container(
        content=login_card,
        alignment=ft.alignment.center,
        expand=True,
        bgcolor=Colors.BG_APP,
    )
