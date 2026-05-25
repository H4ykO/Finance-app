"""
Tema visual centralizado.

POR QUE TER UM ARQUIVO DE TEMA?
Porque cor de marca, espaçamento e fonte aparecem em DEZENAS de lugares
no app. Se eu espalhar "#1A1A1A" hardcoded por toda parte e depois você
quiser trocar para "#101010", vira caça-fantasma.

Centralizando aqui, mudar o visual inteiro é editar um arquivo só.

Paleta de cores do app:
  - Fundo geral creme bem leve (#FAF9F5)
  - Sidebar tom levemente mais escuro (#F4F2EC)
  - Cards brancos com borda sutil
  - Acento roxo (do logo) para botão primário
  - Verde/vermelho semânticos para variação percentual
"""

import flet as ft


# ---------------------------------------------------------------------------
# Cores
# ---------------------------------------------------------------------------
class Colors:
    # Fundos
    BG_APP = "#FAF9F5"          # fundo da área de conteúdo
    BG_SIDEBAR = "#F4F2EC"      # fundo da barra lateral
    BG_CARD = "#FFFFFF"         # cards e painéis
    BG_HOVER = "#EEECE5"        # hover discreto em itens da sidebar

    # Texto
    TEXT_PRIMARY = "#1A1A1A"
    TEXT_SECONDARY = "#6B6B6B"
    TEXT_TERTIARY = "#A0A09B"
    TEXT_ON_DARK = "#FFFFFF"

    # Bordas e divisores
    BORDER = "#E8E6DF"
    DIVIDER = "#EFEDE6"

    # Acentos / marca
    ACCENT = "#7F77DD"          # roxo de destaque
    ACCENT_SOFT = "#EEEDFE"     # roxo bem claro para fundos sutis

    # Semântica
    SUCCESS = "#1D9E75"         # variação positiva ("+20% month over month")
    DANGER = "#D14520"          # variação negativa ("-8% month over month")

    # Botão primário escuro (ex: botão de login)
    DARK = "#1A1A1A"

    # Paleta para gráficos (categorias) — combina com o estilo Anthropic
    CHART_LINE = "#1A1A1A"      # linha do gráfico de despesas mensais
    CHART_GRADIENT = "#F2A623"  # gradiente amarelo embaixo da linha
    CHART_BAR = "#1A1A1A"       # barras pretas em "Week Expenses"


# ---------------------------------------------------------------------------
# Espaçamentos — usar essas constantes em vez de números mágicos
# ---------------------------------------------------------------------------
class Spacing:
    XS = 4
    SM = 8
    MD = 16
    LG = 24
    XL = 32
    XXL = 48


# ---------------------------------------------------------------------------
# Raios de borda
# ---------------------------------------------------------------------------
class Radius:
    SM = 6
    MD = 10
    LG = 14
    XL = 20
    PILL = 999  # botão tipo "pill"


# ---------------------------------------------------------------------------
# Tipografia — tamanhos e pesos consistentes
# ---------------------------------------------------------------------------
class Font:
    # Tamanhos
    SIZE_HUGE = 36       # números grandes dos cards (R$ 2.420,00)
    SIZE_TITLE = 22      # título de seção ("Monthly Expenses")
    SIZE_LARGE = 18
    SIZE_BODY = 14       # corpo de texto padrão
    SIZE_SMALL = 12      # legendas, eixos de gráfico
    SIZE_TINY = 11

    # Pesos
    REGULAR = ft.FontWeight.W_400
    MEDIUM = ft.FontWeight.W_500
    SEMIBOLD = ft.FontWeight.W_600
    BOLD = ft.FontWeight.W_700


# ---------------------------------------------------------------------------
# Helper de formatação monetária — usado em vários lugares
# ---------------------------------------------------------------------------
def format_brl(value: float | int) -> str:
    """
    Formata número como moeda brasileira: 2420 -> 'R$ 2.420,00'

    Por que não usar locale.currency()? Porque depende de o locale
    pt_BR estar instalado no sistema, o que não é garantido. Formatamos
    na mão para ser portátil.
    """
    # f"{value:,.2f}" -> "2,420.00" (formato US)
    # Trocamos . por placeholder, , por ., placeholder por ,
    # para chegar em "2.420,00" (formato BR)
    formatted = f"{float(value):,.2f}"
    # Troca dupla via placeholder evita conflito entre as substituições
    formatted = formatted.replace(",", "_").replace(".", ",").replace("_", ".")
    return f"R$ {formatted}"
