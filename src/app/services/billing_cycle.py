"""
Ciclo de fatura (mês financeiro) do app.

O app não usa o mês de calendário (1 ao último dia). Em vez disso, segue
o ciclo de fatura do cartão, que FECHA no dia 30. Ou seja:

  - Um gasto feito no dia 30 ou depois já entra na fatura do mês seguinte.
  - O "mês financeiro de junho", por exemplo, vai de 30/maio a 29/junho.

Toda a noção de "mês" no app (saldo do mês, cards, bills, analytics,
renda) passa por aqui. Centralizar a régua num único lugar garante que
todos os cálculos concordem — e permite mudar o dia de fechamento no
futuro sem caçar código espalhado.
"""

from datetime import date, timedelta

from dateutil.relativedelta import relativedelta


# Dia em que a fatura fecha. A partir deste dia, os gastos contam para o
# mês financeiro seguinte. Mudar aqui muda a régua do app inteiro.
CLOSING_DAY = 30


def _safe_day(year: int, month: int, day: int) -> date:
    """
    Cria uma data tratando meses que não têm o dia pedido.

    Ex: não existe 30 de fevereiro. Nesse caso, usamos o último dia
    válido do mês (28 ou 29 de fevereiro). Isso mantém o ciclo coerente
    mesmo em fevereiro.
    """
    # Primeiro dia do mês seguinte menos 1 = último dia deste mês
    first_next = (date(year, month, 1) + relativedelta(months=1))
    last_day_of_month = (first_next - timedelta(days=1)).day
    return date(year, month, min(day, last_day_of_month))


def financial_month_of(reference: date) -> date:
    """
    Retorna um marcador (o dia 1 do mês de calendário) que identifica a
    qual mês FINANCEIRO a data `reference` pertence.

    Regra: se o dia for >= CLOSING_DAY, a data pertence ao mês seguinte.

    Ex (fechamento dia 30):
      29/mai -> marcador maio   (1/mai)
      30/mai -> marcador junho  (1/jun)
      15/jun -> marcador junho  (1/jun)
    """
    base = reference.replace(day=1)
    if reference.day >= CLOSING_DAY:
        base = base + relativedelta(months=1)
    return base


def month_bounds(reference: date) -> tuple[date, date]:
    """
    Retorna (primeiro_dia, ultimo_dia) do MÊS FINANCEIRO que contém
    `reference`, respeitando o ciclo de fatura.

    Ex (fechamento dia 30), para uma data em junho:
      início = 30/mai, fim = 29/jun

    O início é sempre o CLOSING_DAY do mês ANTERIOR ao marcador, e o fim
    é o dia anterior ao CLOSING_DAY do mês do marcador. Calcular o início
    no mês anterior (que normalmente tem dia 30) evita o problema de
    fevereiro não ter dia 30.
    """
    marker = financial_month_of(reference)  # dia 1 do mês financeiro
    prev = marker - relativedelta(months=1)  # mês anterior ao marcador
    # Início: dia de fechamento do mês anterior (ex: 30/mai para junho)
    start = _safe_day(prev.year, prev.month, CLOSING_DAY)
    # Fim: dia anterior ao fechamento do mês do marcador (ex: 29/jun)
    end = _safe_day(marker.year, marker.month, CLOSING_DAY) - timedelta(days=1)
    return start, end


def previous_month_bounds(reference: date) -> tuple[date, date]:
    """Retorna os limites do mês financeiro ANTERIOR ao de `reference`."""
    start, _ = month_bounds(reference)
    # Um dia antes do início do mês atual cai no mês financeiro anterior
    return month_bounds(start - timedelta(days=1))


def add_months(reference: date, months: int) -> date:
    """
    Avança/retrocede `months` meses financeiros a partir do marcador de
    `reference`. Usado pelo seletor de mês na tela de Bills.
    """
    marker = financial_month_of(reference)
    return marker + relativedelta(months=months)
