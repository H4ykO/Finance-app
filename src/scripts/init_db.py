"""
Script de inicialização do banco.

Rodar UMA VEZ no início do projeto (ou quando quiser zerar o banco):
    python -m scripts.init_db

O que ele faz:
  1. Cria o arquivo data/finance.db se não existir
  2. Cria todas as tabelas definidas em app/database/models.py
  3. Cria o usuário admin inicial (você)
  4. Cria algumas categorias-padrão para começar

Por que está em `scripts/` e não em `app/`?
Porque é uma ferramenta de ADMIN, rodada manualmente. Não faz parte
do código que roda dentro do app durante o uso normal.
"""

from getpass import getpass

from app.config import settings
from app.database.connection import get_session, init_database
from app.database.models import Category, User
from app.services.user_service import (
    UserAlreadyExistsError,
    create_user,
)


# Categorias padrão com suas cores (roxo/teal/laranja/amarelo)
DEFAULT_CATEGORIES = [
    ("Food",          "#E85D24", "restaurant"),
    ("Transport",     "#1D9E75", "directions_car"),
    ("Leisure",       "#7F77DD", "sports_esports"),
    ("Groceries",     "#F2A623", "shopping_cart"),
    ("Health",        "#D4537E", "local_hospital"),
    ("Housing",       "#378ADD", "home"),
    ("Education",     "#534AB7", "school"),
    ("Other",         "#888780", "category"),
]


def seed_categories() -> None:
    """Insere as categorias-padrão se ainda não existirem."""
    with get_session() as session:
        for name, color, icon in DEFAULT_CATEGORIES:
            existing = session.query(Category).filter_by(name=name).first()
            if existing is None:
                session.add(Category(name=name, color=color, icon=icon))
                print(f"  + Categoria criada: {name}")
        session.commit()


def create_admin_interactively() -> None:
    """
    Cria o admin. Se ADMIN_PASSWORD estiver no .env, usa ela.
    Caso contrário pergunta no terminal.
    """
    email = input("E-mail do admin: ").strip().lower()
    name = input("Seu nome: ").strip()

    if settings.ADMIN_PASSWORD:
        print("Usando ADMIN_PASSWORD do .env")
        password = settings.ADMIN_PASSWORD
    else:
        # getpass não ecoa a senha no terminal — mais seguro que input()
        password = getpass("Senha (não aparecerá enquanto digita): ")
        confirmation = getpass("Confirme a senha: ")
        if password != confirmation:
            print("ERRO: as senhas não coincidem")
            return

    with get_session() as session:
        try:
            user = create_user(
                session=session,
                email=email,
                password=password,
                name=name,
                is_admin=True,
            )
            print(f"\n✓ Admin criado: {user.email} (id={user.id})")
        except UserAlreadyExistsError:
            print(f"\n! Já existe usuário com e-mail {email} — pulando")


def main() -> None:
    print("=" * 60)
    print(" Inicialização do banco — Finance App")
    print("=" * 60)
    print(f"\nBanco: {settings.DATABASE_URL}")

    print("\n[1/3] Criando tabelas...")
    init_database()
    print("      Tabelas criadas/atualizadas.")

    print("\n[2/3] Criando categorias-padrão...")
    seed_categories()

    print("\n[3/3] Criando usuário admin...")
    # Só pede dados de admin se ainda não existir nenhum usuário
    with get_session() as session:
        any_user = session.query(User).first()
    if any_user is None:
        create_admin_interactively()
    else:
        print(f"      Já existe usuário ({any_user.email}) — pulando criação.")

    print("\n" + "=" * 60)
    print(" Pronto! Banco inicializado.")
    print("=" * 60)


if __name__ == "__main__":
    main()
