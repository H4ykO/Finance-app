"""
Tela de Settings (rota "settings").

Foco: status e instruções do bot do Telegram.

Como a configuração sensível (token) fica no .env e o bot roda como
processo separado (scripts/run_bot.py), esta tela é principalmente
INFORMATIVA: mostra se as credenciais estão presentes, qual o ID
autorizado, e o passo a passo para configurar. Não inicia o bot a
partir daqui (o bot é um processo de longa duração, melhor rodado
no terminal).
"""

import flet as ft

from app.config import settings
from app.database.models import User
from app.services.telegram_bot import get_allowed_user_ids
from app.ui.theme import Colors, Font, Radius, Spacing


class SettingsView:
    def __init__(self, page: ft.Page, user: User):
        self.page = page
        self.user = user

    def build(self) -> ft.Control:
        return ft.Container(
            content=ft.Column(
                [
                    ft.Text("Settings", size=Font.SIZE_TITLE, weight=Font.BOLD,
                            color=Colors.TEXT_PRIMARY),
                    ft.Container(height=Spacing.SM),
                    self._telegram_status_card(),
                    self._telegram_howto_card(),
                ],
                spacing=Spacing.MD,
                scroll=ft.ScrollMode.AUTO,
                expand=True,
            ),
            padding=ft.padding.all(Spacing.XL),
            expand=True,
            bgcolor=Colors.BG_APP,
        )

    def _telegram_status_card(self) -> ft.Control:
        token_ok = bool(settings.TELEGRAM_BOT_TOKEN.strip())
        allowed = get_allowed_user_ids()

        def status_row(label: str, ok: bool, detail: str) -> ft.Control:
            icon = ft.Icons.CHECK_CIRCLE if ok else ft.Icons.CANCEL
            color = Colors.SUCCESS if ok else Colors.DANGER
            return ft.Row(
                [
                    ft.Icon(icon, color=color, size=20),
                    ft.Column(
                        [
                            ft.Text(label, size=Font.SIZE_BODY, weight=Font.MEDIUM,
                                    color=Colors.TEXT_PRIMARY),
                            ft.Text(detail, size=Font.SIZE_SMALL, color=Colors.TEXT_SECONDARY),
                        ],
                        spacing=0, expand=True,
                    ),
                ],
                spacing=Spacing.SM,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )

        token_detail = "Configured in .env" if token_ok else "Missing — add TELEGRAM_BOT_TOKEN in .env"
        ids_detail = (
            f"Autorizado(s): {', '.join(str(i) for i in allowed)}"
            if allowed else "Missing — add TELEGRAM_ALLOWED_USER_IDS in .env"
        )

        return ft.Container(
            content=ft.Column(
                [
                    ft.Text("Telegram Bot", size=Font.SIZE_LARGE, weight=Font.SEMIBOLD,
                            color=Colors.TEXT_PRIMARY),
                    ft.Container(height=Spacing.XS),
                    status_row("Bot token", token_ok, token_detail),
                    ft.Divider(height=1, color=Colors.DIVIDER),
                    status_row("Authorized user", bool(allowed), ids_detail),
                    ft.Container(height=Spacing.SM),
                    ft.Container(
                        content=ft.Text(
                            "Para iniciar o bot, rode no terminal:\n"
                            "python -m scripts.run_bot",
                            size=Font.SIZE_SMALL, color=Colors.TEXT_SECONDARY,
                            font_family="monospace",
                        ),
                        bgcolor=Colors.BG_APP,
                        border=ft.border.all(1, Colors.BORDER),
                        border_radius=Radius.MD,
                        padding=Spacing.MD,
                    ),
                ],
                spacing=Spacing.SM,
            ),
            bgcolor=Colors.BG_CARD,
            border=ft.border.all(1, Colors.BORDER),
            border_radius=Radius.LG,
            padding=Spacing.LG,
        )

    def _telegram_howto_card(self) -> ft.Control:
        steps = [
            "1. No Telegram, procure @BotFather e mande /newbot.",
            "2. Escolha um nome e um username (termina em 'bot').",
            "3. Copie o token e cole em TELEGRAM_BOT_TOKEN no arquivo .env.",
            "4. Procure @userinfobot, mande qualquer mensagem, copie seu ID.",
            "5. Cole o ID em TELEGRAM_ALLOWED_USER_IDS no .env.",
            "6. Rode 'python -m scripts.run_bot' no terminal.",
            "7. Mande uma mensagem ao seu bot, ex: '45,90 uber'.",
        ]
        return ft.Container(
            content=ft.Column(
                [
                    ft.Text("How to set up", size=Font.SIZE_LARGE, weight=Font.SEMIBOLD,
                            color=Colors.TEXT_PRIMARY),
                    ft.Container(height=Spacing.XS),
                    *[
                        ft.Text(s, size=Font.SIZE_BODY, color=Colors.TEXT_SECONDARY)
                        for s in steps
                    ],
                ],
                spacing=Spacing.SM,
            ),
            bgcolor=Colors.BG_CARD,
            border=ft.border.all(1, Colors.BORDER),
            border_radius=Radius.LG,
            padding=Spacing.LG,
        )
