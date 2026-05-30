"""
Service de análises (analytics).

Agrega os dados de transações em números úteis para a tela de análises:
  - gastos por categoria num período (para o gráfico de pizza)
  - série de gastos/renda mês a mês ao longo do ano (para comparação)
  - comparação de um período com o anterior

Tudo aqui é cálculo puro sobre o banco — sem UI — então é testável
isoladamente. A tela de análises só consome o que estas funções devolvem.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.models import Category, Transaction
from app.services.transaction_service import sum_expenses_in_period
from app.services import billing_cycle


# ---------------------------------------------------------------------------
# Estruturas de retorno
# ---------------------------------------------------------------------------
@dataclass
class CategorySlice:
    """Uma fatia do gráfico de pizza: categoria + total + % do total."""
    category_name: str
    color: str
    total: Decimal
    percent: float  # 0-100


@dataclass
class PeriodComparison:
    """Comparação de um período com o anterior."""
    current: Decimal
    previous: Decimal
    percent_change: Optional[float]  # None se não há base anterior


@dataclass
class MonthlyPoint:
    """Um ponto na série mensal: mês + gastos + renda."""
    year: int
    month: int
    expenses: Decimal
    income: Decimal

    @property
    def label(self) -> str:
        """Rótulo curto tipo '03/26'."""
        return f"{self.month:02d}/{str(self.year)[2:]}"


# ---------------------------------------------------------------------------
# Helpers de período
# ---------------------------------------------------------------------------
def _month_bounds(reference: date) -> tuple[date, date]:
    """Limites do mês financeiro (ciclo de fatura) — ver billing_cycle."""
    return billing_cycle.month_bounds(reference)


def period_bounds(kind: str, reference: date) -> tuple[date, date]:
    """
    Retorna (início, fim) de um período a partir de uma data de referência.

    kind: "daily" (o dia), "weekly" (seg-dom da semana), "monthly" (o mês),
          "yearly" (o ano).
    """
    if kind == "daily":
        return reference, reference
    if kind == "weekly":
        # Semana começa na segunda-feira
        start = reference - timedelta(days=reference.weekday())
        return start, start + timedelta(days=6)
    if kind == "monthly":
        return _month_bounds(reference)
    if kind == "yearly":
        return date(reference.year, 1, 1), date(reference.year, 12, 31)
    raise ValueError(f"Período desconhecido: {kind}")


def previous_period_bounds(kind: str, reference: date) -> tuple[date, date]:
    """Retorna (início, fim) do período ANTERIOR ao de referência."""
    start, _ = period_bounds(kind, reference)
    if kind == "daily":
        prev = start - timedelta(days=1)
        return prev, prev
    if kind == "weekly":
        prev = start - timedelta(days=7)
        return prev, prev + timedelta(days=6)
    if kind == "monthly":
        last_prev = start - timedelta(days=1)
        return _month_bounds(last_prev)
    if kind == "yearly":
        return date(start.year - 1, 1, 1), date(start.year - 1, 12, 31)
    raise ValueError(f"Período desconhecido: {kind}")


# ---------------------------------------------------------------------------
# Gastos por categoria (gráfico de pizza)
# ---------------------------------------------------------------------------
def expenses_by_category(
    session: Session,
    user_id: int,
    start: date,
    end: date,
) -> list[CategorySlice]:
    """
    Soma os gastos por categoria no período, ordenado do maior para o menor.

    Transações sem categoria entram como "Uncategorized". Cada fatia traz
    o percentual sobre o total de gastos do período.
    """
    # Soma por category_id
    stmt = (
        select(
            Transaction.category_id,
            func.sum(Transaction.amount),
        )
        .where(
            Transaction.user_id == user_id,
            Transaction.kind == "expense",
            Transaction.occurred_at >= start,
            Transaction.occurred_at <= end,
        )
        .group_by(Transaction.category_id)
    )
    rows = session.execute(stmt).all()

    total = sum((amount for _, amount in rows), Decimal("0"))
    if total == 0:
        return []

    # Mapa de categorias (id -> nome, cor)
    cats = {c.id: (c.name, c.color) for c in session.scalars(select(Category)).all()}

    slices: list[CategorySlice] = []
    for cat_id, amount in rows:
        if cat_id is None:
            name, color = "Uncategorized", "#888780"
        else:
            name, color = cats.get(cat_id, ("Uncategorized", "#888780"))
        percent = float(amount / total * 100)
        slices.append(CategorySlice(name, color, amount, percent))

    slices.sort(key=lambda s: s.total, reverse=True)
    return slices


# ---------------------------------------------------------------------------
# Comparação de período (atual vs anterior)
# ---------------------------------------------------------------------------
def compare_expenses(
    session: Session,
    user_id: int,
    kind: str,
    reference: date,
) -> PeriodComparison:
    """Compara o total de gastos do período atual com o período anterior."""
    cur_start, cur_end = period_bounds(kind, reference)
    prev_start, prev_end = previous_period_bounds(kind, reference)

    current = sum_expenses_in_period(session, user_id, cur_start, cur_end)
    previous = sum_expenses_in_period(session, user_id, prev_start, prev_end)

    if previous == 0:
        pct = None
    else:
        pct = float((current - previous) / previous * 100)

    return PeriodComparison(current=current, previous=previous, percent_change=pct)


# ---------------------------------------------------------------------------
# Série mensal (para o ano)
# ---------------------------------------------------------------------------
def monthly_series(
    session: Session,
    user_id: int,
    year: int,
) -> list[MonthlyPoint]:
    """
    Retorna 12 pontos (jan-dez) com gastos e renda de cada mês do ano.

    Meses sem movimento aparecem com zero — assim o gráfico mostra o ano
    inteiro de forma consistente.
    """
    points: list[MonthlyPoint] = []
    for month in range(1, 13):
        first = date(year, month, 1)
        last = _month_bounds(first)[1]

        expenses = sum_expenses_in_period(session, user_id, first, last)

        income = session.scalar(
            select(func.sum(Transaction.amount)).where(
                Transaction.user_id == user_id,
                Transaction.kind == "income",
                Transaction.occurred_at >= first,
                Transaction.occurred_at <= last,
            )
        ) or Decimal("0")

        points.append(MonthlyPoint(year=year, month=month,
                                   expenses=expenses, income=income))
    return points
