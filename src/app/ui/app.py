"""
Controller principal do app Flet.

Responsabilidades:
  - Configurar a `Page` (título, tema, dimensões iniciais)
  - Manter o estado do usuário logado
  - Trocar entre as views (login, dashboard, etc.)

POR QUE UMA CLASSE E NÃO FUNÇÕES SOLTAS?
Porque o "estado" do app (qual usuário está logado, qual rota está
ativa) precisa ser compartilhado entre callbacks. Numa classe, o
estado vive nos atributos da instância e os métodos têm acesso natural.
"""

from typing import Optional

import flet as ft

from app.database.connection import ensure_seed_data, needs_initial_setup, get_session
from app.database.models import User
from app.services import user_service, session_service
from app.ui.components.sidebar import build_sidebar
from app.ui.theme import Colors
from app.ui.views.analytics_view import AnalyticsView
from app.ui.views.bills_view import BillsView
from app.ui.views.categories_view import CategoriesView
from app.ui.views.dashboard_view import build_dashboard_view
from app.ui.views.history_view import HistoryView
from app.ui.views.home_view import HomeView
from app.ui.views.login_view import build_login_view
from app.ui.views.signup_view import build_signup_view
from app.ui.views.settings_view import SettingsView
from app.ui.views.pin_view import build_pin_view


class FinanceApp:
    """Orquestra as views do app."""

    def __init__(self, page: ft.Page):
        self.page = page
        self.current_user: Optional[User] = None
        self.current_route: str = "home"  # rota padrão após login

    # -----------------------------------------------------------------------
    # Entry point
    # -----------------------------------------------------------------------
    def start(self) -> None:
        """Configura a página e exibe a primeira tela apropriada."""
        self._configure_page()
        ensure_seed_data()

        # Primeira abertura de todas (sem usuário) -> cadastro.
        if needs_initial_setup():
            self._show_signup()
            return

        # Se o usuário já tem PIN E a sessão de boot continua válida
        # (o PC não reiniciou desde o último login completo), pede só o PIN.
        # Caso contrário, exige o login completo (e-mail + senha).
        with get_session() as s:
            user = user_service.get_single_user(s)
            user_id = user.id if user else None
            tem_pin = user_service.has_pin(s, user_id) if user_id else False

        if user_id and tem_pin and session_service.is_session_valid(user_id):
            self._show_pin()
        else:
            self._show_login()

    # -----------------------------------------------------------------------
    # Configuração inicial da Page
    # -----------------------------------------------------------------------
    def _configure_page(self) -> None:
        page = self.page
        page.title = "Finance App"
        page.bgcolor = Colors.BG_APP
        # Dimensões iniciais — pensadas para Mac (mas redimensionáveis)
        page.window.width = 1400
        page.window.height = 900
        page.window.min_width = 1100
        page.window.min_height = 700
        # Centraliza a janela na tela ao abrir (senão o sistema decide,
        # e costuma abrir descentralizada).
        page.window.center()
        # Tira o padding default da página — controlamos espaçamentos internamente
        page.padding = 0
        # Tema do Material Design — claro e com fonte sans
        page.theme_mode = ft.ThemeMode.LIGHT
        page.theme = ft.Theme(
            font_family="SF Pro Display",  # Mac usa esta por padrão; fallback automático
        )
        page.fonts = {}

    # -----------------------------------------------------------------------
    # Renderização de views
    # -----------------------------------------------------------------------
    def _show_login(self) -> None:
        """Limpa a tela e mostra o login."""
        self.page.controls.clear()
        login = build_login_view(self.page, on_login_success=self._on_login_success)
        self.page.add(login)
        self.page.update()

    def _show_signup(self) -> None:
        """Mostra a tela de cadastro inicial (primeira abertura)."""
        self.page.controls.clear()
        signup = build_signup_view(self.page, on_signup_success=self._on_login_success)
        self.page.add(signup)
        self.page.update()

    def _show_main_layout(self) -> None:
        """
        Mostra o layout principal (sidebar + área de conteúdo).
        A área de conteúdo é determinada por `self.current_route`.
        """
        assert self.current_user is not None

        # Conteúdo central baseado na rota
        content = self._build_content_for_route()

        # Sidebar à esquerda + conteúdo à direita
        layout = ft.Row(
            [
                build_sidebar(
                    current_route=self.current_route,
                    on_navigate=self._on_navigate,
                    on_logout=self._on_logout,
                ),
                # `expand=True` no container faz o conteúdo ocupar todo o
                # espaço restante após a sidebar
                ft.Container(content=content, expand=True),
            ],
            spacing=0,
            expand=True,
            vertical_alignment=ft.CrossAxisAlignment.STRETCH,
        )

        self.page.controls.clear()
        self.page.add(layout)
        self.page.update()

    def _build_content_for_route(self) -> ft.Control:
        """
        Retorna o controle Flet correspondente à rota atual.
        """
        if self.current_route == "home":
            return HomeView(self.page, self.current_user, self._on_navigate).build()
        if self.current_route == "dashboard":
            return build_dashboard_view(self.current_user, self.page)
        if self.current_route == "transactions":
            # Views com estado são CLASSES; instanciamos e chamamos build()
            return HistoryView(self.page, self.current_user).build()
        if self.current_route == "bills":
            return BillsView(self.page, self.current_user).build()
        if self.current_route == "categories":
            return CategoriesView(self.page, self.current_user).build()
        if self.current_route == "analytics":
            return AnalyticsView(self.page, self.current_user).build()
        if self.current_route == "settings":
            return SettingsView(self.page, self.current_user).build()
        return self._placeholder_view(self.current_route)

    def _placeholder_view(self, route: str) -> ft.Control:
        """Tela genérica para rotas ainda não implementadas."""
        return ft.Container(
            content=ft.Column(
                [
                    ft.Icon(
                        ft.Icons.CONSTRUCTION_OUTLINED,
                        size=64,
                        color=Colors.TEXT_TERTIARY,
                    ),
                    ft.Text(
                        f"View '{route}' under construction",
                        size=22,
                        color=Colors.TEXT_SECONDARY,
                    ),
                    ft.Text(
                        "Coming in a future phase.",
                        size=14,
                        color=Colors.TEXT_TERTIARY,
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=12,
            ),
            alignment=ft.alignment.center,
            expand=True,
            bgcolor=Colors.BG_APP,
        )

    # -----------------------------------------------------------------------
    # Callbacks
    # -----------------------------------------------------------------------
    def _on_login_success(self, user: User) -> None:
        self.current_user = user
        self.current_route = "home"
        # Marca esta sessão de boot como autenticada — habilita o PIN nas
        # próximas aberturas até o PC reiniciar.
        session_service.mark_authenticated(user.id)
        # Se o usuário ainda não configurou um PIN, oferece criar um agora.
        with get_session() as s:
            tem_pin = user_service.has_pin(s, user.id)
        if not tem_pin:
            self._offer_create_pin()
        else:
            self._show_main_layout()

    def _show_pin(self) -> None:
        """Mostra a tela de PIN (acesso rápido)."""
        self.page.controls.clear()
        pin_view = build_pin_view(
            self.page,
            on_pin_success=self._on_pin_success,
            on_use_password=self._show_login,  # "esqueci/usar senha" cai no login
        )
        self.page.add(pin_view)
        self.page.update()

    def _on_pin_success(self) -> None:
        """PIN correto: carrega o usuário e entra no app."""
        with get_session() as s:
            user = user_service.get_single_user(s)
            s.expunge(user)
        self.current_user = user
        self.current_route = "home"
        self._show_main_layout()

    def _offer_create_pin(self) -> None:
        """
        Após o primeiro login, pergunta se o usuário quer criar um PIN de
        acesso rápido. Ele pode pular e seguir só com senha.
        """
        pin_field = ft.TextField(
            label="Choose a PIN (4–8 digits)",
            password=True, can_reveal_password=True,
            keyboard_type=ft.KeyboardType.NUMBER,
            border_color=Colors.BORDER,
        )
        error_text = ft.Text("", color=Colors.DANGER, size=12, visible=False)

        def save_pin(e):
            pin = (pin_field.value or "").strip()
            if not (pin.isdigit() and 4 <= len(pin) <= 8):
                error_text.value = "PIN must be 4 to 8 digits."
                error_text.visible = True
                error_text.update()
                return
            with get_session() as s:
                user_service.set_pin(s, self.current_user.id, pin)
            self.page.close(dialog)
            self._show_main_layout()

        def skip(e):
            self.page.close(dialog)
            self._show_main_layout()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Set up quick access?"),
            content=ft.Container(
                content=ft.Column([
                    ft.Text("Create a PIN to reopen the app faster. You'll still "
                            "need your password after restarting your computer.",
                            size=13, color=Colors.TEXT_SECONDARY),
                    pin_field, error_text,
                ], tight=True, spacing=12, width=360),
            ),
            actions=[
                ft.TextButton(content=ft.Text("Skip", color=Colors.TEXT_SECONDARY), on_click=skip),
                ft.TextButton(content=ft.Text("Save PIN", color=Colors.ACCENT,
                              weight=ft.FontWeight.W_600), on_click=save_pin),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        # Precisa estar na página antes de abrir o dialog
        self.page.add(ft.Container())
        self.page.open(dialog)

    def _on_navigate(self, route: str) -> None:
        if route == self.current_route:
            return  # já está aqui, evita re-render desnecessário
        self.current_route = route
        self._show_main_layout()

    def _on_logout(self) -> None:
        self.current_user = None
        self.current_route = "home"  # reseta para o default
        # Logout explícito invalida a sessão de PIN — exige senha de novo.
        session_service.clear_session()
        self._show_login()
