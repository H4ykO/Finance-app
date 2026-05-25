"""
Service do dashboard — calcula tudo que aparece nos cards e gráficos
da tela principal.

Por que existe um service só para isso?
Para que a view (Flet) seja "burra": ela apenas pede os números prontos
e renderiza. Toda a aritmética e queries ficam aqui. Isso torna a UI
mais legível e os cálculos testáveis.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.database.models import Bill, Income
from app.services.transaction_service import (
    sum_expenses_in_period,
    sum_expenses_by_day,
    sum_expenses_by_week,
    list_recent_transactions,
)


# ---------------------------------------------------------------------------
# Estruturas de dados — usamos dataclasses para retornar dados estruturados
# ---------------------------------------------------------------------------
# Por que dataclass e não dict?
# 1. O editor sabe os campos (autocomplete funciona)
# 2. Erro de digitação vira erro de Python, não bug silencioso
# 3. Imutabilidade opcional via frozen=True
@dataclass
class StatCardData:
    """Dados para um dos 3 cards do topo (Available, Bills, Income)."""
    label: str
    amount: Decimal
    variation_percent: Optional[float]  # None se não dá pra calcular
    variation_is_positive_good: bool    # True para Available/Income, False para Bills
                                        # afeta cor: positivo bom = verde, ruim = vermelho


@dataclass
class DashboardData:
    """Tudo que o dashboard precisa, calculado de uma vez."""
    available: StatCardData
    bills: StatCardData
    income: StatCardData
    monthly_expenses_by_day: list[tuple[date, Decimal]]
    weekly_expenses: list[tuple[date, Decimal]]
    recent_transactions: list  # list[Transaction], mas evita import circular


# ---------------------------------------------------------------------------
# Helpers de variação percentual
# ---------------------------------------------------------------------------
def _percent_change(current: Decimal, previous: Decimal) -> Optional[float]:
    """
    Calcula variação percentual entre dois valores.

    Retorna None quando `previous` é zero (divisão por zero não tem
    significado — preferimos não mostrar nada a mostrar "infinito%").
    """
    if previous == 0:
        return None
    return float((current - previous) / previous * 100)


def _month_bounds(reference: date) -> tuple[date, date]:
    """Retorna (primeiro_dia, ultimo_dia) do mês contendo `reference`."""
    first = reference.replace(day=1)
    # Truque: dia 28 + 4 dias entra no mês seguinte, depois voltamos
    # ao dia 1 e tiramos 1 dia. Funciona para qualquer mês, incluindo fevereiro.
    next_month = (first + timedelta(days=32)).replace(day=1)
    last = next_month - timedelta(days=1)
    return first, last


def _previous_month_bounds(reference: date) -> tuple[date, date]:
    """Retorna (primeiro_dia, ultimo_dia) do MÊS ANTERIOR."""
    first_this_month, _ = _month_bounds(reference)
    last_prev_month = first_this_month - timedelta(days=1)
    return _month_bounds(last_prev_month)


# ---------------------------------------------------------------------------
# Cards individuais
# ---------------------------------------------------------------------------
def _build_available_card(session: Session, user_id: int, today: date) -> StatCardData:
    """
    Card "Available" — quanto sobra livre depois dos compromissos.

    Fórmula:  Available = renda do mês − gastos do mês − contas NÃO pagas

    A ideia: o "Available" reserva o que ainda está comprometido
    (assinaturas e outras contas em aberto), mostrando o que de fato
    está livre. Diferente do "Month balance" da Home, que é só o fluxo
    do mês (renda − gastos).

    DETALHE IMPORTANTE — por que pagar uma conta NÃO muda o Available:
    quando você paga uma conta, ela sai de "contas não pagas" (deixa de
    ser descontada aqui) mas, como o pagamento é registrado como gasto,
    entra em "gastos do mês" (passa a ser descontada ali). A subtração
    só troca de lugar; o total fica igual. Por isso é essencial que
    pagar uma conta sempre a registre como gasto (ver bill_service).

    As contas não pagas consideradas são apenas as que vencem no MÊS
    VIGENTE (item 4) — contas de junho só contam em junho, etc.
    """
    first_this, last_this = _month_bounds(today)
    first_prev, last_prev = _previous_month_bounds(today)

    # Renda e gastos do mês
    income_this = _total_income_in_period(session, user_id, first_this, last_this)
    expense_this = sum_expenses_in_period(session, user_id, first_this, last_this)

    # Contas não pagas que vencem no MÊS VIGENTE (não mais "qualquer mês").
    unpaid_bills = session.scalar(
        select(func.sum(Bill.amount)).where(
            Bill.user_id == user_id,
            Bill.is_paid == False,  # noqa: E712
            Bill.due_date >= first_this,
            Bill.due_date <= last_this,
        )
    ) or Decimal("0")

    current = income_this - expense_this - unpaid_bills

    # Mês anterior (variação): bills não pagas que venceram no mês anterior.
    income_prev = _total_income_in_period(session, user_id, first_prev, last_prev)
    expense_prev = sum_expenses_in_period(session, user_id, first_prev, last_prev)
    unpaid_bills_prev = session.scalar(
        select(func.sum(Bill.amount)).where(
            Bill.user_id == user_id,
            Bill.is_paid == False,  # noqa: E712
            Bill.due_date >= first_prev,
            Bill.due_date <= last_prev,
        )
    ) or Decimal("0")
    previous = income_prev - expense_prev - unpaid_bills_prev

    return StatCardData(
        label="Available",
        amount=current,
        variation_percent=_percent_change(current, previous),
        variation_is_positive_good=True,
    )


def _build_bills_card(session: Session, user_id: int, today: date) -> StatCardData:
    """
    Card "Bills" — total das contas não pagas que vencem no MÊS VIGENTE.

    Item 4: contas só contam no mês do vencimento. Uma conta que vence
    em julho não aparece aqui em junho — só quando chegar julho.
    A variação compara com o total pago dentro do mês atual.
    """
    first_this, last_this = _month_bounds(today)

    # Total em aberto que vence NESTE mês
    current = session.scalar(
        select(func.sum(Bill.amount)).where(
            Bill.user_id == user_id,
            Bill.is_paid == False,  # noqa: E712
            Bill.due_date >= first_this,
            Bill.due_date <= last_this,
        )
    ) or Decimal("0")

    # Referência de variação: total pago no mês atual
    previous = session.scalar(
        select(func.sum(Bill.amount)).where(
            Bill.user_id == user_id,
            Bill.is_paid == True,  # noqa: E712
            Bill.paid_at >= first_this,
            Bill.paid_at <= last_this,
        )
    ) or Decimal("0")

    return StatCardData(
        label="Bills",
        amount=current,
        variation_percent=_percent_change(current, previous),
        # Para Bills, aumentar é tecnicamente "ruim" (mais a pagar), mas
        # tratamos a variação como neutra/positiva visualmente — mais
        # bills pode refletir mais atividade, e evita poluir a tela de
        # vermelho. Decisão de UX.
        variation_is_positive_good=True,
    )


def _total_income_in_period(
    session: Session, user_id: int, start: date, end: date
) -> Decimal:
    """
    Renda total de um período = tabela Income + transações com kind=income.

    Centralizar esse cálculo aqui garante que o card Income, o card Saldo
    e a Home usem exatamente a mesma definição de "renda", evitando que
    números divirjam entre as telas.
    """
    from app.database.models import Transaction

    income_table = session.scalar(
        select(func.sum(Income.amount)).where(
            Income.user_id == user_id,
            Income.received_at >= start,
            Income.received_at <= end,
        )
    ) or Decimal("0")

    income_tx = session.scalar(
        select(func.sum(Transaction.amount)).where(
            Transaction.user_id == user_id,
            Transaction.kind == "income",
            Transaction.occurred_at >= start,
            Transaction.occurred_at <= end,
        )
    ) or Decimal("0")

    return income_table + income_tx


def _build_income_card(session: Session, user_id: int, today: date) -> StatCardData:
    """Card "Income" — renda total do mês (Income + entradas), vs mês anterior."""
    first_this, last_this = _month_bounds(today)
    first_prev, last_prev = _previous_month_bounds(today)

    current = _total_income_in_period(session, user_id, first_this, last_this)
    previous = _total_income_in_period(session, user_id, first_prev, last_prev)

    return StatCardData(
        label="Income",
        amount=current,
        variation_percent=_percent_change(current, previous),
        variation_is_positive_good=True,
    )





# ---------------------------------------------------------------------------
# Função principal — única chamada feita pela view
# ---------------------------------------------------------------------------
def build_dashboard(
    session: Session,
    user_id: int,
    today: Optional[date] = None,
) -> DashboardData:
    """
    Monta TODO o dashboard em uma só passada.

    `today` é parametrizável para facilitar testes — em produção
    usamos a data atual.
    """
    if today is None:
        today = date.today()

    # Determina qual mês mostrar nos gráficos. Idealmente o mês atual,
    # mas se ele não tiver transações (ex: você importou dados de meses
    # passados), usamos o mês da transação mais recente — assim o
    # dashboard nunca abre vazio sem motivo.
    reference_day = today
    latest_tx = list_recent_transactions(session=session, user_id=user_id, limit=1)
    first_this_month, _ = _month_bounds(today)
    has_current_month_data = bool(
        sum_expenses_by_day(session, user_id, first_this_month, today)
    )
    if not has_current_month_data and latest_tx:
        # Pula para o mês da transação mais recente
        reference_day = latest_tx[0].occurred_at

    first_ref_month, last_ref_month = _month_bounds(reference_day)
    # Limita o fim ao "hoje" se o mês de referência for o atual
    end_for_daily = min(last_ref_month, today) if reference_day == today else last_ref_month

    # Gastos do mês de referência, por dia (para o gráfico de linha)
    daily_map = sum_expenses_by_day(
        session=session,
        user_id=user_id,
        start=first_ref_month,
        end=end_for_daily,
    )
    monthly_expenses_by_day = sorted(daily_map.items())

    # Gastos por semana nas últimas 12 semanas a partir do mês de referência
    weekly = sum_expenses_by_week(
        session=session,
        user_id=user_id,
        end=last_ref_month,
        weeks=12,
    )

    # Últimas transações (tabela "Last purchases")
    recent = list_recent_transactions(
        session=session,
        user_id=user_id,
        limit=8,
    )

    return DashboardData(
        available=_build_available_card(session, user_id, today),
        bills=_build_bills_card(session, user_id, today),
        income=_build_income_card(session, user_id, today),
        monthly_expenses_by_day=monthly_expenses_by_day,
        weekly_expenses=weekly,
        recent_transactions=recent,
    )
