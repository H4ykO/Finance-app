"""
Sidebar: barra lateral fixa de navegação.

Barra lateral estreita (~80px), com ícones de navegação empilhados.
O item ativo fica com fundo preto e ícone branco; os outros são cinza
e clicáveis.
"""

from dataclasses import dataclass
from typing import Callable

import flet as ft

from app.ui.theme import Colors, Radius, Spacing


@dataclass
class NavItem:
    """Representa um item da sidebar — ícone + identificador da rota."""
    icon: str          # nome do ícone Material (ex: "home", "grid_view")
    route: str         # identificador interno (ex: "dashboard")
    tooltip: str = ""  # texto que aparece no hover


# Ordem dos itens de navegação (de cima para baixo).
# `grid_view_outlined` é o item ativo no screenshot (ícone de pontinhos 2x2).
NAV_ITEMS: list[NavItem] = [
    NavItem(icon=ft.Icons.HOME_OUTLINED, route="home", tooltip="Home"),
    NavItem(icon=ft.Icons.GRID_VIEW_OUTLINED, route="dashboard", tooltip="Dashboard"),
    NavItem(icon=ft.Icons.INVENTORY_2_OUTLINED, route="transactions", tooltip="History"),
    NavItem(icon=ft.Icons.RECEIPT_LONG_OUTLINED, route="bills", tooltip="Bills"),
    NavItem(icon=ft.Icons.LABEL_OUTLINE, route="categories", tooltip="Categories"),
    NavItem(icon=ft.Icons.TRENDING_UP_OUTLINED, route="analytics", tooltip="Analytics"),
    NavItem(icon=ft.Icons.SETTINGS_OUTLINED, route="settings", tooltip="Settings"),
]


def build_sidebar(
    current_route: str,
    on_navigate: Callable[[str], None],
    on_logout: Callable[[], None],
) -> ft.Container:
    """
    Constrói a sidebar.

    Recebe a rota ativa (para destacar o item certo) e dois callbacks:
    o que fazer quando o usuário clica num item de navegação, e
    o que fazer quando clica em sair.

    Repare como passamos FUNÇÕES de fora em vez de chamar o controller
    diretamente: isso mantém o componente desacoplado — ele não precisa
    saber de onde veio nem para onde vai.
    """

    def make_icon_button(item: NavItem) -> ft.Control:
        is_active = item.route == current_route

        # Item ativo: fundo escuro, ícone branco
        # Item inativo: sem fundo, ícone cinza, com hover sutil
        bg = Colors.DARK if is_active else "transparent"
        fg = Colors.TEXT_ON_DARK if is_active else Colors.TEXT_SECONDARY

        return ft.Container(
            content=ft.Icon(item.icon, color=fg, size=22),
            width=44,
            height=44,
            bgcolor=bg,
            border_radius=Radius.MD,
            alignment=ft.alignment.center,
            tooltip=item.tooltip,
            # `on_click` aceita uma função que recebe o evento `e`;
            # ignoramos o evento e disparamos o callback de navegação
            on_click=lambda e, route=item.route: on_navigate(route),
            # Cursor de mão indica clicável
            ink=True,  # efeito ripple do Material ao clicar
        )

    # Logo no topo: mini gráfico de barras (mesmo do ícone do app),
    # sem o fundo escuro — só as barras verdes em ascensão.
    def _bar(height: int, opacity: float) -> ft.Container:
        return ft.Container(
            width=5, height=height,
            bgcolor="#34E0A1", opacity=opacity,
            border_radius=2,
        )

    logo = ft.Container(
        content=ft.Row(
            [
                _bar(10, 0.55),
                _bar(16, 0.70),
                _bar(22, 0.85),
                _bar(28, 1.0),
            ],
            spacing=3,
            alignment=ft.MainAxisAlignment.CENTER,
            vertical_alignment=ft.CrossAxisAlignment.END,
        ),
        padding=ft.padding.only(bottom=Spacing.MD),
        alignment=ft.alignment.center,
        height=36,
    )

    # Botão de logout — visualmente diferenciado no rodapé
    logout_button = ft.Container(
        content=ft.Icon(
            ft.Icons.LOGOUT_OUTLINED,
            color=Colors.ACCENT,
            size=20,
        ),
        width=44, height=44,
        bgcolor=Colors.ACCENT_SOFT,
        border_radius=Radius.MD,
        alignment=ft.alignment.center,
        tooltip="Log out",
        on_click=lambda e: on_logout(),
        ink=True,
    )

    # Coluna principal: logo + ícones agrupados em cima, logout no rodapé
    return ft.Container(
        content=ft.Column(
            [
                logo,
                # Coluna dos itens de navegação
                ft.Column(
                    [make_icon_button(item) for item in NAV_ITEMS],
                    spacing=Spacing.SM,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                # Espaço expansível empurra o logout para baixo
                ft.Container(expand=True),
                logout_button,
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=Spacing.MD,
        ),
        width=80,
        bgcolor=Colors.BG_SIDEBAR,
        padding=ft.padding.symmetric(vertical=Spacing.LG, horizontal=Spacing.MD),
        # Borda direita sutil para separar visualmente do conteúdo
        border=ft.border.only(right=ft.BorderSide(1, Colors.BORDER)),
    )
