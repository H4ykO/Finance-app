"""
Limpa os dados financeiros, preservando usuário e categorias.

Uso:
    python -m scripts.reset_data

APAGA: transações, contas a pagar (bills), rendas (incomes), saldos
       (available_balance) e as regras de categorização.
PRESERVA: seu usuário/login e as categorias.

Útil para recomeçar do zero e reimportar o CSV limpo.

SEGURANÇA: pede confirmação DUPLA porque é destrutivo e irreversível.
"""

from app.database.connection import get_session, init_database
from app.database.models import (
    Bill,
    CategoryRule,
    Income,
    Transaction,
    User,
)


def main() -> None:
    init_database()

    with get_session() as session:
        user = session.query(User).first()
        if user is None:
            print("Nenhum usuário no banco. Nada a fazer.")
            return
        user_id = user.id
        user_email = user.email

        n_tx = session.query(Transaction).filter_by(user_id=user_id).count()
        n_bills = session.query(Bill).filter_by(user_id=user_id).count()
        n_inc = session.query(Income).filter_by(user_id=user_id).count()
        n_rules = session.query(CategoryRule).filter_by(user_id=user_id).count()

    print("=" * 60)
    print(" Reset de dados — Finance App")
    print("=" * 60)
    print(f"\nUsuário: {user_email}")
    print("\nSerá APAGADO (irreversível):")
    print(f"  - {n_tx} transações")
    print(f"  - {n_bills} contas a pagar")
    print(f"  - {n_inc} rendas")
    print(f"  - {n_rules} regras de categorização")
    print("\nSerá PRESERVADO: seu login e as categorias.")

    if n_tx + n_bills + n_inc + n_rules == 0:
        print("\nNada para apagar. Banco já está limpo.")
        return

    # Confirmação dupla
    print()
    c1 = input("Tem certeza? Digite 'sim' para continuar: ").strip().lower()
    if c1 != "sim":
        print("Cancelado.")
        return
    c2 = input("Confirme novamente digitando 'APAGAR': ").strip()
    if c2 != "APAGAR":
        print("Cancelado.")
        return

    with get_session() as session:
        session.query(Transaction).filter_by(user_id=user_id).delete()
        session.query(Bill).filter_by(user_id=user_id).delete()
        session.query(Income).filter_by(user_id=user_id).delete()
        session.query(CategoryRule).filter_by(user_id=user_id).delete()
        session.commit()

    print("\n✓ Dados apagados. Reimporte seu CSV com:")
    print("  python -m scripts.import_my_csv ~/Downloads/transactions.csv")


if __name__ == "__main__":
    main()
