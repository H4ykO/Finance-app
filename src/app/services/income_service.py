"""
Service de Income (renda).

Atende ao pedido de uma forma MINIMALISTA de ajustar a renda do mês
atual. A filosofia aqui é: "uma renda principal por mês, fácil de
editar". Nada de gerenciar dezenas de entradas — só o número que
aparece no card "Income" do dashboard.

COMO FUNCIONA:
Tratamos a renda do mês como um valor único editável. Internamente,
mantemos uma entrada Income marcada como "principal" (is_recurring=True)
para o mês. Quando você ajusta, atualizamos essa entrada em vez de
criar várias — assim o card sempre reflete o último valor definido.

Se você quiser registrar rendas extras (freelance, presente) no
futuro, a tabela suporta, mas a UI minimalista foca na renda principal.
"""

from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import Income
from app.services import billing_cycle


def _month_bounds(reference: date) -> tuple[date, date]:
    """Limites do mês financeiro (ciclo de fatura) — ver billing_cycle."""
    return billing_cycle.month_bounds(reference)


def get_current_month_income(
    session: Session,
    user_id: int,
    today: Optional[date] = None,
) -> Decimal:
    """
    Retorna a renda TOTAL registrada no mês atual.

    Soma todas as entradas Income do mês — assim, se houver a renda
    principal mais alguma extra, o total reflete tudo.
    """
    if today is None:
        today = date.today()
    first, last = _month_bounds(today)

    rows = session.scalars(
        select(Income).where(
            Income.user_id == user_id,
            Income.received_at >= first,
            Income.received_at <= last,
        )
    ).all()

    return sum((r.amount for r in rows), Decimal("0"))


def set_current_month_income(
    session: Session,
    user_id: int,
    amount: Decimal,
    today: Optional[date] = None,
) -> Income:
    """
    Define a renda principal do mês atual.

    Comportamento idempotente: se já existe uma entrada "principal"
    (is_recurring=True) neste mês, ATUALIZA seu valor. Senão, cria uma.

    Isso evita o problema de criar uma entrada nova toda vez que você
    ajusta o número, o que inflaria o total artificialmente.
    """
    if today is None:
        today = date.today()
    first, last = _month_bounds(today)

    # Procura a entrada principal do mês
    principal = session.scalar(
        select(Income).where(
            Income.user_id == user_id,
            Income.is_recurring == True,  # noqa: E712
            Income.received_at >= first,
            Income.received_at <= last,
        )
    )

    if principal is not None:
        # Atualiza a existente
        principal.amount = amount
        session.commit()
        session.refresh(principal)
        return principal

    # Cria nova entrada principal, datada de hoje
    principal = Income(
        user_id=user_id,
        description="Renda do mês",
        amount=amount,
        received_at=today,
        is_recurring=True,
    )
    session.add(principal)
    session.commit()
    session.refresh(principal)
    return principal
