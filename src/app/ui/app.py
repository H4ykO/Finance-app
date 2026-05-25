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

from app.database.connection import ensure_seed_data, needs_initial_setup
from app.database.models import User
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
        # Garante que as categorias padrão existem (essencial no .app,
        # onde não se roda o script init_db pelo terminal).
        ensure_seed_data()
        # Primeira abertura (sem usuário) -> cadastro. Senão -> login.
        if needs_initial_setup():
            self._show_signup()
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
        self._show_main_layout()

    def _on_navigate(self, route: str) -> None:
        if route == self.current_route:
            return  # já está aqui, evita re-render desnecessário
        self.current_route = route
        self._show_main_layout()

    def _on_logout(self) -> None:
        self.current_user = None
        self.current_route = "home"  # reseta para o default
        self._show_login()
