"""
Service de Bills (contas a pagar).

Atende ao pedido: gerenciar contas a pagar como se fossem "compras
agendadas", com adicionar, remover e marcar como paga.

DIFERENÇA ENTRE BILL E TRANSACTION:
  - Bill      = compromisso FUTURO ("vou pagar R$ 200 de luz dia 15")
  - Transaction = movimento que JÁ aconteceu ("paguei R$ 197 de luz")

Quando você marca uma bill como paga, opcionalmente criamos uma
Transaction correspondente — assim a conta paga entra no histórico
e nos gráficos de gasto.
"""

from datetime import date
from decimal import Decimal
from typing import Optional

from dateutil.relativedelta import relativedelta
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import Bill, Transaction
from app.services.categorizer import guess_category_name
from app.database.models import Category


def _month_bounds(reference: date) -> tuple[date, date]:
    """Primeiro e último dia do mês de `reference`."""
    first = reference.replace(day=1)
    # Vai para o primeiro dia do mês seguinte e volta um dia
    next_month = first + relativedelta(months=1)
    last = next_month - relativedelta(days=1)
    return first, last


def list_bills(
    session: Session,
    user_id: int,
    only_unpaid: bool = False,
    month: Optional[date] = None,
) -> list[Bill]:
    """
    Lista as contas do usuário, ordenadas por vencimento.

    `only_unpaid=True` filtra só as ainda não pagas.
    `month` (qualquer data dentro do mês) filtra só contas que vencem
    naquele mês — usado para mostrar "as contas do mês vigente".
    """
    stmt = select(Bill).where(Bill.user_id == user_id)
    if only_unpaid:
        stmt = stmt.where(Bill.is_paid == False)  # noqa: E712 (SQLAlchemy exige ==)
    if month is not None:
        first, last = _month_bounds(month)
        stmt = stmt.where(Bill.due_date >= first, Bill.due_date <= last)
    stmt = stmt.order_by(Bill.due_date.asc())
    return list(session.scalars(stmt).all())


def create_bill(
    session: Session,
    user_id: int,
    description: str,
    amount: Decimal,
    due_date: date,
    is_recurring: bool = False,
) -> Bill:
    """
    Cria uma nova conta a pagar.

    `is_recurring=True` marca a conta como assinatura recorrente: ao
    pagá-la, o app gera automaticamente uma nova instância para o mês
    seguinte (ver mark_bill_paid).
    """
    bill = Bill(
        user_id=user_id,
        description=description.strip(),
        amount=amount,
        due_date=due_date,
        is_paid=False,
        is_recurring=is_recurring,
    )
    session.add(bill)
    session.commit()
    session.refresh(bill)
    return bill


def duplicate_bill_to_next_month(
    session: Session,
    bill_id: int,
    user_id: int,
) -> Optional[Bill]:
    """
    Cria uma cópia da conta com vencimento um mês depois (item 5).

    Mecanismo MANUAL: o usuário clica em "duplicar" e ganha uma cópia
    no mês seguinte, não paga, que ele pode então editar (mudar a data,
    valor, etc.). Diferente da recorrência automática.
    """
    original = session.get(Bill, bill_id)
    if original is None or original.user_id != user_id:
        return None
    nova = Bill(
        user_id=user_id,
        description=original.description,
        amount=original.amount,
        due_date=original.due_date + relativedelta(months=1),
        is_paid=False,
        is_recurring=original.is_recurring,
    )
    session.add(nova)
    session.commit()
    session.refresh(nova)
    return nova


def delete_bill(session: Session, bill_id: int, user_id: int) -> bool:
    """Remove uma conta. Retorna True se removeu."""
    bill = session.get(Bill, bill_id)
    if bill is None or bill.user_id != user_id:
        return False
    session.delete(bill)
    session.commit()
    return True


def mark_bill_paid(
    session: Session,
    bill_id: int,
    user_id: int,
    register_as_transaction: bool = True,
    paid_on: Optional[date] = None,
) -> Optional[Bill]:
    """
    Marca uma conta como paga e a registra como gasto.

    O registro como gasto agora é PADRÃO (register_as_transaction=True).
    Isso é essencial para o card "Available" se manter estável ao pagar:
    a conta sai de "contas não pagas" mas entra em "gastos", então o
    valor disponível não muda — só o "Month balance" reflete o gasto.

    O parâmetro continua existindo (pode ser desligado em casos especiais),
    mas o padrão é registrar.
    """
    bill = session.get(Bill, bill_id)
    if bill is None or bill.user_id != user_id:
        return None

    if paid_on is None:
        paid_on = date.today()

    bill.is_paid = True
    bill.paid_at = paid_on

    if register_as_transaction:
        # Categoriza automaticamente pela descrição
        cat_name = guess_category_name(bill.description)
        category = session.scalar(
            select(Category).where(Category.name == cat_name)
        )
        tx = Transaction(
            user_id=user_id,
            category_id=category.id if category else None,
            description=f"[Bill] {bill.description}",
            amount=bill.amount,
            kind="expense",
            occurred_at=paid_on,
            source="manual",
            notes="Auto-generated when paying a bill.",
        )
        session.add(tx)

    # Recorrência (item 6): ao pagar uma assinatura recorrente, geramos
    # automaticamente a próxima instância, com vencimento um mês depois.
    # Assim a assinatura "some" do mês atual (vira gasto) e "reaparece"
    # no mês seguinte, pronta para ser paga de novo.
    # A nova instância NÃO é recorrente em si — ela carrega a flag para
    # continuar o ciclo, mas só gera a próxima quando for paga.
    if bill.is_recurring:
        proxima = Bill(
            user_id=user_id,
            description=bill.description,
            amount=bill.amount,
            due_date=bill.due_date + relativedelta(months=1),
            is_paid=False,
            is_recurring=True,
        )
        session.add(proxima)

    session.commit()
    session.refresh(bill)
    return bill


def mark_bill_unpaid(session: Session, bill_id: int, user_id: int) -> Optional[Bill]:
    """
    Desfaz o pagamento (volta para não paga).

    Nota: NÃO removemos a transação que possa ter sido criada — fazer
    isso automaticamente seria arriscado (e se o usuário editou ela?).
    Removê-la fica a cargo do usuário na tela de Histórico.
    """
    bill = session.get(Bill, bill_id)
    if bill is None or bill.user_id != user_id:
        return None
    bill.is_paid = False
    bill.paid_at = None
    session.commit()
    session.refresh(bill)
    return bill
