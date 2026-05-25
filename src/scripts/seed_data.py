"""
Script de seed: popula o banco com dados fake REALISTAS para visualizar
o dashboard cheio durante o desenvolvimento.

Rodar:
    python -m scripts.seed_data

Idempotente: se já existem transações para o usuário, pergunta se
você quer apagar e recriar. Não toca em outros usuários.
"""

import random
from datetime import date, timedelta
from decimal import Decimal

from app.database.connection import get_session, init_database
from app.database.models import (
    Bill,
    Category,
    Income,
    Transaction,
    User,
)


# Estabelecimentos comuns por categoria (para gerar descrições realistas)
ESTABELECIMENTOS = {
    "Alimentação": [
        "iFood — Sushi Yassu", "Rappi — Burger King", "iFood — Pizza Hut",
        "Outback Steakhouse", "Padaria Bella Paulista", "Sttarbucks Shopping",
        "Açaí no Ponto", "iFood — China in Box",
    ],
    "Transporte": [
        "Uber", "99 POP", "Posto Shell Avenida", "Posto Ipiranga",
        "Estacionamento Shopping", "Metrô SP",
    ],
    "Lazer": [
        "Netflix", "Spotify Premium", "Cinemark", "Steam — DLC",
        "PlayStation Store", "Showpass",
    ],
    "Mercado": [
        "Pão de Açúcar", "Carrefour Express", "Hortifruti Natural",
        "Sams Club", "Atacadão",
    ],
    "Saúde": [
        "Drogasil", "Drogaria SP", "Consulta Dr. Silva", "Academia Smart Fit",
    ],
    "Moradia": [
        "Conta de Luz CPFL", "Internet Vivo Fibra", "Gás Ultragaz", "IPTU",
    ],
    "Educação": [
        "Udemy — Curso Python", "Livro Amazon", "Notion AI",
    ],
    "Outros": [
        "Amazon — Acessórios", "Mercado Livre", "AliExpress", "Saque Caixa 24h",
    ],
}


def _pick_user() -> User:
    """Pega o primeiro usuário (admin) do banco."""
    with get_session() as session:
        user = session.query(User).first()
        if user is None:
            raise RuntimeError(
                "Nenhum usuário no banco. Rode primeiro: python -m scripts.init_db"
            )
        session.expunge(user)
    return user


def _confirm_wipe(user_id: int) -> bool:
    """Se já existem transações, pergunta se deve apagar antes de re-seedar."""
    with get_session() as session:
        existing = session.query(Transaction).filter_by(user_id=user_id).count()
    if existing == 0:
        return True

    print(f"Já existem {existing} transações para este usuário.")
    answer = input("Apagar e recriar? [s/N]: ").strip().lower()
    if answer != "s":
        return False

    with get_session() as session:
        session.query(Transaction).filter_by(user_id=user_id).delete()
        session.query(Bill).filter_by(user_id=user_id).delete()
        session.query(Income).filter_by(user_id=user_id).delete()
        session.commit()
    print("  Dados anteriores apagados.")
    return True


def _seed_transactions(user_id: int, categories: list[Category]) -> None:
    """
    Cria ~80 transações dos últimos 100 dias, com distribuição realista.

    Cada dia tem 0-3 transações, valores entre R$ 15 e R$ 350,
    categoria escolhida com peso (alimentação aparece mais).
    """
    # Pesos para tornar a distribuição mais realista
    category_weights = {
        "Alimentação": 35,
        "Transporte": 20,
        "Mercado": 15,
        "Lazer": 10,
        "Saúde": 5,
        "Moradia": 5,  # poucas mas grandes
        "Educação": 4,
        "Outros": 6,
    }

    cat_by_name = {c.name: c for c in categories}

    transactions: list[Transaction] = []
    today = date.today()

    for days_ago in range(100):
        d = today - timedelta(days=days_ago)
        # Mais transações em dias úteis, menos em domingo
        num_txs = random.choices([0, 1, 2, 3], weights=[20, 40, 30, 10])[0]
        if d.weekday() == 6:  # domingo
            num_txs = max(0, num_txs - 1)

        for _ in range(num_txs):
            cat_name = random.choices(
                list(category_weights.keys()),
                weights=list(category_weights.values()),
            )[0]
            cat = cat_by_name[cat_name]

            # Valor varia por categoria
            if cat_name == "Moradia":
                amount = Decimal(str(random.uniform(150, 900))).quantize(Decimal("0.01"))
            elif cat_name == "Mercado":
                amount = Decimal(str(random.uniform(80, 350))).quantize(Decimal("0.01"))
            else:
                amount = Decimal(str(random.uniform(15, 180))).quantize(Decimal("0.01"))

            descricao = random.choice(ESTABELECIMENTOS[cat_name])

            transactions.append(
                Transaction(
                    user_id=user_id,
                    category_id=cat.id,
                    description=descricao,
                    amount=amount,
                    kind="expense",
                    occurred_at=d,
                    source="manual",  # como se fosse importado manualmente
                )
            )

    with get_session() as session:
        session.add_all(transactions)
        session.commit()
    print(f"  + {len(transactions)} transações criadas")


def _seed_bills(user_id: int) -> None:
    """Cria contas do mês atual e do mês passado."""
    today = date.today()
    first_this = today.replace(day=1)
    first_prev = (first_this - timedelta(days=1)).replace(day=1)

    bills = [
        # Mês atual
        Bill(user_id=user_id, description="Aluguel",  amount=Decimal("1450.00"),
             due_date=first_this + timedelta(days=4), is_paid=False),
        Bill(user_id=user_id, description="Luz",      amount=Decimal("180.00"),
             due_date=first_this + timedelta(days=9), is_paid=False),
        Bill(user_id=user_id, description="Internet", amount=Decimal("120.00"),
             due_date=first_this + timedelta(days=14), is_paid=False),
        Bill(user_id=user_id, description="Cartão",   amount=Decimal("200.00"),
             due_date=first_this + timedelta(days=19), is_paid=False),

        # Mês passado (para calcular variação %)
        Bill(user_id=user_id, description="Aluguel",  amount=Decimal("1450.00"),
             due_date=first_prev + timedelta(days=4), is_paid=True,
             paid_at=first_prev + timedelta(days=4)),
        Bill(user_id=user_id, description="Internet", amount=Decimal("120.00"),
             due_date=first_prev + timedelta(days=14), is_paid=True),
    ]

    with get_session() as session:
        session.add_all(bills)
        session.commit()
    print(f"  + {len(bills)} contas criadas (4 este mês, 2 passado)")


def _seed_incomes(user_id: int) -> None:
    """Salário recente — este mês e passado."""
    today = date.today()
    first_this = today.replace(day=1)
    first_prev = (first_this - timedelta(days=1)).replace(day=1)

    incomes = [
        Income(user_id=user_id, description="Salário",
               amount=Decimal("4350.00"),
               received_at=first_this + timedelta(days=4),
               is_recurring=True),
        Income(user_id=user_id, description="Salário",
               amount=Decimal("4730.00"),
               received_at=first_prev + timedelta(days=4),
               is_recurring=True),
    ]

    with get_session() as session:
        session.add_all(incomes)
        session.commit()
    print(f"  + {len(incomes)} entradas de renda criadas")



def main() -> None:
    print("=" * 60)
    print(" Seed de dados de exemplo — Finance App")
    print("=" * 60)

    init_database()  # garante que as tabelas existem
    user = _pick_user()
    print(f"\nUsuário alvo: {user.email}")

    if not _confirm_wipe(user.id):
        print("Cancelado.")
        return

    # Pega as categorias criadas pelo init_db
    with get_session() as session:
        categories = session.query(Category).all()
        if not categories:
            print("ERRO: não há categorias. Rode primeiro: python -m scripts.init_db")
            return
        # Detacha para usar fora da sessão
        for c in categories:
            session.expunge(c)

    print("\nCriando dados fake...")
    _seed_transactions(user.id, categories)
    _seed_bills(user.id)
    _seed_incomes(user.id)

    print("\n" + "=" * 60)
    print(" Pronto! Rode `python main.py` para ver o dashboard preenchido.")
    print("=" * 60)


if __name__ == "__main__":
    # Seed com a mesma semente para resultados reprodutíveis em dev
    random.seed(42)
    main()
