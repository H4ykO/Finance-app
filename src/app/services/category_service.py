"""
Service de categorias e regras de categorização.

Duas responsabilidades:
  1. CRUD de categorias (criar/editar/remover)
  2. CRUD de regras "descrição -> categoria" criadas pelo usuário

Ao remover uma categoria que tem transações, movemos essas transações
para "Outros" (não apagamos). Isso evita perda de dados e mantém o
histórico íntegro.
"""

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import Category, CategoryRule, Transaction


# Nome da categoria de fallback para onde transações órfãs vão
FALLBACK_CATEGORY_NAME = "Other"


# ---------------------------------------------------------------------------
# Categorias
# ---------------------------------------------------------------------------
def list_categories(session: Session) -> list[Category]:
    """Todas as categorias, ordenadas por nome."""
    return list(session.scalars(select(Category).order_by(Category.name)).all())


def create_category(
    session: Session,
    name: str,
    color: str = "#888780",
    icon: str = "category",
) -> Category:
    """Cria uma categoria nova. Lança ValueError se o nome já existir."""
    name = name.strip()
    if not name:
        raise ValueError("O nome da categoria não pode ser vazio.")

    existing = session.scalar(select(Category).where(Category.name == name))
    if existing is not None:
        raise ValueError(f"Já existe uma categoria chamada '{name}'.")

    cat = Category(name=name, color=color, icon=icon)
    session.add(cat)
    session.commit()
    session.refresh(cat)
    return cat


def update_category(
    session: Session,
    category_id: int,
    name: Optional[str] = None,
    color: Optional[str] = None,
    icon: Optional[str] = None,
) -> Optional[Category]:
    """Edita campos de uma categoria. Retorna a categoria ou None se não achar."""
    cat = session.get(Category, category_id)
    if cat is None:
        return None

    if name is not None:
        new_name = name.strip()
        if new_name and new_name != cat.name:
            # Verifica conflito de nome
            conflict = session.scalar(
                select(Category).where(Category.name == new_name, Category.id != category_id)
            )
            if conflict is not None:
                raise ValueError(f"Já existe uma categoria chamada '{new_name}'.")
            cat.name = new_name
    if color is not None:
        cat.color = color
    if icon is not None:
        cat.icon = icon

    session.commit()
    session.refresh(cat)
    return cat


def delete_category(session: Session, category_id: int) -> tuple[bool, int]:
    """
    Remove uma categoria, movendo suas transações para "Outros".

    Retorna (sucesso, qtd_transacoes_movidas).

    Regras de proteção:
      - Não deixa remover a própria "Outros" (é o destino de fallback)
      - Move transações e remove regras associadas antes de deletar
    """
    cat = session.get(Category, category_id)
    if cat is None:
        return False, 0

    if cat.name == FALLBACK_CATEGORY_NAME:
        raise ValueError(f"A categoria '{FALLBACK_CATEGORY_NAME}' não pode ser removida.")

    # Acha a categoria de fallback
    fallback = session.scalar(select(Category).where(Category.name == FALLBACK_CATEGORY_NAME))
    fallback_id = fallback.id if fallback else None

    # Conta e move transações
    moved = 0
    txs = session.scalars(
        select(Transaction).where(Transaction.category_id == category_id)
    ).all()
    for tx in txs:
        tx.category_id = fallback_id
        moved += 1

    # Força a persistência da reatribuição ANTES de deletar a categoria.
    # Sem isso, o relationship Category.transactions faz o SQLAlchemy
    # "desassociar" as transações (category_id=None) ao deletar, sobrescrevendo
    # nossa reatribuição para o fallback.
    session.flush()

    # Remove regras que apontavam para esta categoria
    rules = session.scalars(
        select(CategoryRule).where(CategoryRule.category_id == category_id)
    ).all()
    for r in rules:
        session.delete(r)

    session.flush()
    session.delete(cat)
    session.commit()
    return True, moved


# ---------------------------------------------------------------------------
# Regras de categorização (do usuário)
# ---------------------------------------------------------------------------
def list_rules(session: Session, user_id: int) -> list[CategoryRule]:
    """Lista as regras do usuário, com a categoria carregada."""
    from sqlalchemy.orm import joinedload
    stmt = (
        select(CategoryRule)
        .where(CategoryRule.user_id == user_id)
        .options(joinedload(CategoryRule.category))
        .order_by(CategoryRule.pattern)
    )
    return list(session.scalars(stmt).all())


def create_rule(
    session: Session,
    user_id: int,
    pattern: str,
    category_id: int,
) -> CategoryRule:
    """Cria uma regra 'pattern -> categoria'."""
    pattern = pattern.strip()
    if not pattern:
        raise ValueError("O padrão da regra não pode ser vazio.")

    rule = CategoryRule(user_id=user_id, pattern=pattern, category_id=category_id)
    session.add(rule)
    session.commit()
    session.refresh(rule)
    return rule


def delete_rule(session: Session, rule_id: int, user_id: int) -> bool:
    """Remove uma regra. Retorna True se removeu."""
    rule = session.get(CategoryRule, rule_id)
    if rule is None or rule.user_id != user_id:
        return False
    session.delete(rule)
    session.commit()
    return True


def get_user_rules_map(session: Session, user_id: int) -> list[tuple[str, str]]:
    """
    Retorna as regras do usuário como lista de (pattern_maiusculo, nome_categoria).

    Usado pelo categorizador. Ordenado por tamanho do pattern (maiores
    primeiro) para que regras mais específicas tenham prioridade.
    """
    from sqlalchemy.orm import joinedload
    rules = session.scalars(
        select(CategoryRule)
        .where(CategoryRule.user_id == user_id)
        .options(joinedload(CategoryRule.category))
    ).all()
    pairs = [(r.pattern.upper(), r.category.name) for r in rules if r.category]
    # Pattern mais longo = mais específico = prioridade
    pairs.sort(key=lambda p: len(p[0]), reverse=True)
    return pairs
