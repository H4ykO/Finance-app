"""
Service de transações — operações que envolvem a tabela `transactions`.

Mantém o mesmo padrão do user_service: funções que recebem `session`
de fora (dependency injection) e retornam objetos do banco.
"""

from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.orm import Session, joinedload

from app.database.models import Transaction


def list_recent_transactions(
    session: Session,
    user_id: int,
    limit: int = 10,
) -> list[Transaction]:
    """
    Retorna as N transações mais recentes do usuário.

    `joinedload(Transaction.category)` faz JOIN com a tabela `categories`
    em uma única query, evitando o problema do "N+1": sem isso, acessar
    `tx.category.name` em loop dispararia N queries adicionais.
    """
    stmt = (
        select(Transaction)
        .where(Transaction.user_id == user_id)
        .options(joinedload(Transaction.category))
        .order_by(Transaction.occurred_at.desc(), Transaction.id.desc())
        .limit(limit)
    )
    return list(session.scalars(stmt).all())


def sum_expenses_by_day(
    session: Session,
    user_id: int,
    start: date,
    end: date,
) -> dict[date, Decimal]:
    """
    Soma de despesas agrupadas por dia.

    Retorna {date(2026,5,1): Decimal('120.50'), ...}.
    Útil para o gráfico "Monthly Expenses".

    Por que fazer a soma no banco em vez de em Python?
    Performance — o SQLite faz a agregação muito mais rápido que iterar
    centenas de linhas no Python, especialmente quando o banco crescer.
    """
    stmt = (
        select(
            Transaction.occurred_at,
            func.sum(Transaction.amount).label("total"),
        )
        .where(
            Transaction.user_id == user_id,
            Transaction.kind == "expense",
            Transaction.occurred_at >= start,
            Transaction.occurred_at <= end,
        )
        .group_by(Transaction.occurred_at)
        .order_by(Transaction.occurred_at.asc())
    )

    result: dict[date, Decimal] = {}
    for occurred_at, total in session.execute(stmt):
        result[occurred_at] = total or Decimal("0")
    return result


def sum_expenses_in_period(
    session: Session,
    user_id: int,
    start: date,
    end: date,
) -> Decimal:
    """Soma total de despesas no período. Retorna Decimal('0') se vazio."""
    stmt = select(func.sum(Transaction.amount)).where(
        Transaction.user_id == user_id,
        Transaction.kind == "expense",
        Transaction.occurred_at >= start,
        Transaction.occurred_at <= end,
    )
    result = session.scalar(stmt)
    return result if result is not None else Decimal("0")


def sum_expenses_by_week(
    session: Session,
    user_id: int,
    end: date,
    weeks: int = 12,
) -> list[tuple[date, Decimal]]:
    """
    Soma de despesas agrupadas pelas últimas N semanas.

    Retorna lista de (segunda-feira_da_semana, total) ordenada da
    mais antiga para a mais recente. Útil para o gráfico
    "Week Expenses".

    Fazemos a agregação em Python (não SQL) porque "semana" envolve
    cálculo de data que varia entre bancos. Em SQLite, strftime
    funcionaria, mas a portabilidade compensa o custo extra.
    """
    # Calcula a segunda-feira da semana de `end` como ponto final
    end_monday = end - timedelta(days=end.weekday())
    start_monday = end_monday - timedelta(weeks=weeks - 1)
    start_date = start_monday  # primeira segunda do intervalo

    # Busca todas as transações no intervalo
    stmt = select(Transaction.occurred_at, Transaction.amount).where(
        Transaction.user_id == user_id,
        Transaction.kind == "expense",
        Transaction.occurred_at >= start_date,
        Transaction.occurred_at <= end,
    )

    # Inicializa o dicionário com TODAS as semanas zeradas
    # (para que semanas sem gastos apareçam como 0 no gráfico, não sumam)
    buckets: dict[date, Decimal] = {}
    cursor = start_monday
    for _ in range(weeks):
        buckets[cursor] = Decimal("0")
        cursor += timedelta(days=7)

    # Soma cada transação na semana correta
    for occurred_at, amount in session.execute(stmt):
        week_start = occurred_at - timedelta(days=occurred_at.weekday())
        if week_start in buckets:
            buckets[week_start] += amount

    return sorted(buckets.items())


# ===========================================================================
# Busca, filtros e CRUD manual de transações
# ===========================================================================

def search_transactions(
    session: Session,
    user_id: int,
    text: Optional[str] = None,
    kind: Optional[str] = None,
    category_id: Optional[int] = None,
    start: Optional[date] = None,
    end: Optional[date] = None,
    limit: int = 500,
) -> list[Transaction]:
    """
    Busca transações com filtros combináveis (todos opcionais).

    - text: filtra por substring na descrição (case-insensitive)
    - kind: "expense" ou "income"
    - category_id: id de categoria específica
    - start / end: intervalo de datas (inclusive)
    - limit: teto de resultados (proteção contra carregar 10k linhas na UI)

    Os filtros se ACUMULAM (lógica AND). Passar None em um filtro = ignorá-lo.
    Construímos a query incrementalmente: começamos com a base e vamos
    adicionando .where() conforme os filtros fornecidos.
    """
    stmt = (
        select(Transaction)
        .where(Transaction.user_id == user_id)
        .options(joinedload(Transaction.category))
    )

    if text:
        # ilike = LIKE case-insensitive; % são curingas (qualquer coisa antes/depois)
        stmt = stmt.where(Transaction.description.ilike(f"%{text}%"))
    if kind:
        stmt = stmt.where(Transaction.kind == kind)
    if category_id is not None:
        stmt = stmt.where(Transaction.category_id == category_id)
    if start is not None:
        stmt = stmt.where(Transaction.occurred_at >= start)
    if end is not None:
        stmt = stmt.where(Transaction.occurred_at <= end)

    stmt = stmt.order_by(
        Transaction.occurred_at.desc(), Transaction.id.desc()
    ).limit(limit)

    return list(session.scalars(stmt).all())


def create_transaction(
    session: Session,
    user_id: int,
    description: str,
    amount: Decimal,
    kind: str,
    occurred_at: date,
    category_id: Optional[int] = None,
    notes: Optional[str] = None,
) -> Transaction:
    """
    Cria uma transação manualmente (formulário da tela de Histórico).

    `source="manual"` marca que veio de inserção pela UI, não de importação.
    Não geramos external_id (manuais não têm risco de duplicação por reimport).
    """
    tx = Transaction(
        user_id=user_id,
        category_id=category_id,
        description=description.strip(),
        amount=amount,
        kind=kind,
        occurred_at=occurred_at,
        source="manual",
        notes=notes,
    )
    session.add(tx)
    session.commit()
    session.refresh(tx)
    return tx


def update_transaction(
    session: Session,
    transaction_id: int,
    user_id: int,
    **fields,
) -> Optional[Transaction]:
    """
    Atualiza campos de uma transação existente.

    `**fields` aceita: description, amount, kind, occurred_at,
    category_id, notes. Só atualiza os que forem passados.

    Retorna a transação atualizada, ou None se não encontrada
    (ou se pertencer a outro usuário — proteção de acesso).
    """
    tx = session.get(Transaction, transaction_id)
    if tx is None or tx.user_id != user_id:
        return None

    # Lista branca de campos editáveis — evita que alguém injete
    # user_id ou id via **fields
    allowed = {"description", "amount", "kind", "occurred_at", "category_id", "notes"}
    for key, value in fields.items():
        if key in allowed:
            setattr(tx, key, value)

    session.commit()
    session.refresh(tx)
    return tx


def delete_transaction(
    session: Session,
    transaction_id: int,
    user_id: int,
) -> bool:
    """
    Remove uma transação. Retorna True se removeu, False se não achou.

    Verificamos user_id para garantir que um usuário não apague
    transação de outro.
    """
    tx = session.get(Transaction, transaction_id)
    if tx is None or tx.user_id != user_id:
        return False
    session.delete(tx)
    session.commit()
    return True


def recategorize_similar(
    session: Session,
    user_id: int,
    description: str,
    category_id: Optional[int],
) -> int:
    """
    Aplica uma categoria a TODAS as transações do usuário cuja descrição
    contém o mesmo texto (case-insensitive).

    Usado pela edição no Histórico com "tornar padrão": ao mudar a
    categoria de "McDonalds", aplica a todas as transações com "McDonalds"
    na descrição. Retorna a quantidade afetada.
    """
    text = description.strip()
    if not text:
        return 0

    stmt = select(Transaction).where(
        Transaction.user_id == user_id,
        Transaction.description.ilike(f"%{text}%"),
    )
    rows = list(session.scalars(stmt).all())
    for tx in rows:
        tx.category_id = category_id
    session.commit()
    return len(rows)


def export_month_to_csv(
    session: Session,
    user_id: int,
    reference: date,
    category_names: dict,
) -> str:
    """
    Gera o conteúdo CSV das transações do MÊS FINANCEIRO de `reference`.

    Respeita o ciclo de fatura (ver billing_cycle). Colunas:
    date, title, amount, kind, category.

    `category_names` é um dict {category_id: nome} para resolver o nome
    da categoria sem novas queries.

    Retorna o texto do CSV (quem chama grava em arquivo).
    """
    import csv
    import io
    from app.services import billing_cycle

    start, end = billing_cycle.month_bounds(reference)
    stmt = (
        select(Transaction)
        .where(
            Transaction.user_id == user_id,
            Transaction.occurred_at >= start,
            Transaction.occurred_at <= end,
        )
        .order_by(Transaction.occurred_at.asc(), Transaction.id.asc())
    )
    rows = list(session.scalars(stmt).all())

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["date", "title", "amount", "kind", "category"])
    for tx in rows:
        writer.writerow([
            tx.occurred_at.strftime("%Y-%m-%d"),
            tx.description,
            f"{tx.amount:.2f}",
            tx.kind,
            category_names.get(tx.category_id, ""),
        ])
    return buffer.getvalue()
