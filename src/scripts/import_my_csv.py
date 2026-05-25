"""
Importa um CSV de extrato real para o banco, pela linha de comando.

Uso:
    python -m scripts.import_my_csv caminho/para/transactions.csv

É um atalho de terminal para a mesma lógica do botão "Importar CSV"
da tela de Histórico. Útil para a primeira carga de dados, ou para
quem prefere o terminal.

Idempotente: graças à deduplicação por external_id, rodar duas vezes
com o mesmo arquivo não duplica nada.
"""

import sys
from pathlib import Path

from app.database.connection import get_session, init_database
from app.database.models import User
from app.services.csv_importer import import_csv_text


def main() -> None:
    if len(sys.argv) < 2:
        print("Uso: python -m scripts.import_my_csv <caminho_do_csv>")
        sys.exit(1)

    csv_path = Path(sys.argv[1])
    if not csv_path.exists():
        print(f"Arquivo não encontrado: {csv_path}")
        sys.exit(1)

    init_database()

    # Pega o primeiro usuário (admin). Em um app multiusuário, receberíamos
    # o e-mail como argumento; para uso pessoal, o admin basta.
    with get_session() as session:
        user = session.query(User).first()
        if user is None:
            print("Nenhum usuário no banco. Rode antes: python -m scripts.init_db")
            sys.exit(1)
        user_id = user.id
        user_email = user.email

    print(f"Importando '{csv_path.name}' para o usuário {user_email}...")

    text = csv_path.read_text(encoding="utf-8")
    with get_session() as session:
        result = import_csv_text(session, user_id, text)

    print(f"\nResultado: {result.summary()}")
    print(f"Total de linhas lidas: {result.total_rows}")
    if result.errors:
        print(f"\nErros ({len(result.errors)}):")
        for err in result.errors[:10]:
            print(f"  - {err}")
        if len(result.errors) > 10:
            print(f"  ... e mais {len(result.errors) - 10} erros")


if __name__ == "__main__":
    main()
