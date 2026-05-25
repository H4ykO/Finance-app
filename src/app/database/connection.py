"""
Conexão e gerenciamento de sessões com o banco de dados.

Conceitos importantes do SQLAlchemy 2.x:

- ENGINE: é o "motor" que sabe falar o dialeto do banco (SQLite, Postgres...).
  É caro de criar — criamos UM por aplicativo e reutilizamos.

- SESSION: é uma "conversa" com o banco. Você abre, faz operações
  (insert, update, query), e fecha. Cada operação isolada do usuário
  (ex: criar uma transação) tipicamente usa uma sessão própria.

- BASE: é a classe-mãe de todos os modelos. SQLAlchemy usa ela para
  saber quais tabelas existem e gerar SQL automaticamente.
"""

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


# ---------------------------------------------------------------------------
# Engine — uma instância para toda a aplicação
# ---------------------------------------------------------------------------
# echo=False: não imprime SQL no console. Mude para True quando estiver
# debugando para ver tudo que está sendo executado.
#
# connect_args={"check_same_thread": False}: SQLite por padrão só aceita
# conexões da thread que abriu. Como o Flet pode usar várias threads,
# desativamos essa proteção. Em produção com Postgres isso não existe.
engine = create_engine(
    settings.DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
)


# ---------------------------------------------------------------------------
# Session factory — fábrica de sessões
# ---------------------------------------------------------------------------
# sessionmaker(...) retorna uma CLASSE; chamamos SessionLocal() para criar
# uma sessão concreta.
#
# autocommit=False: nada é salvo até chamarmos session.commit() explicitamente.
# autoflush=False: o SQLAlchemy não joga mudanças no banco em momentos
# inesperados; nós controlamos quando.
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,  # objetos continuam usáveis após commit
)


# ---------------------------------------------------------------------------
# Base — classe-mãe de todos os modelos
# ---------------------------------------------------------------------------
class Base(DeclarativeBase):
    """
    Todos os modelos (User, Transaction, etc.) vão herdar desta classe.

    No SQLAlchemy 2.x usamos DeclarativeBase em vez do antigo
    declarative_base(). É mais limpo e tem suporte melhor a type hints.
    """
    pass


# ---------------------------------------------------------------------------
# Helper para usar sessão com `with` — garante fechamento mesmo se der erro
# ---------------------------------------------------------------------------
@contextmanager
def get_session() -> Iterator[Session]:
    """
    Context manager que entrega uma sessão e garante que ela será fechada.

    Uso:
        with get_session() as session:
            user = session.query(User).first()
            # session é fechada automaticamente ao sair do bloco

    O `yield` entrega a sessão para o bloco `with`. Se der exceção,
    fazemos rollback (desfaz tudo). Se sair normal, fechamos.
    """
    session = SessionLocal()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_database() -> None:
    """
    Cria todas as tabelas definidas nos modelos.

    Esta função importa os modelos para que o SQLAlchemy "veja" todas
    as classes que herdam de Base, e então cria as tabelas no banco.

    Em projetos maiores usaríamos Alembic para migrações versionadas,
    mas para uso pessoal create_all() é suficiente.
    """
    # Import local (dentro da função) para evitar import circular:
    # models.py importa Base daqui, então não podemos importar models
    # no topo deste arquivo.
    from app.database import models  # noqa: F401  (registra os modelos em Base)

    Base.metadata.create_all(bind=engine)

    # Migração leve: adiciona colunas novas a tabelas já existentes.
    # O create_all() acima cria tabelas que não existem, mas NÃO altera
    # tabelas existentes. Para bancos antigos (criados antes de um campo
    # novo), adicionamos a coluna manualmente se ela faltar — assim não
    # perdemos os dados já gravados.
    _run_light_migrations()


def _run_light_migrations() -> None:
    """
    Adiciona colunas novas a tabelas existentes, de forma idempotente.

    Para uso pessoal com SQLite, isto substitui um sistema de migração
    completo (Alembic). Cada migração verifica se a coluna já existe
    antes de tentar criá-la.
    """
    from sqlalchemy import text

    # Mapa: tabela -> lista de (coluna, definição SQL) que devem existir
    migrations = {
        "bills": [
            ("is_recurring", "BOOLEAN NOT NULL DEFAULT 0"),
        ],
    }

    with engine.begin() as conn:
        for table, columns in migrations.items():
            # Descobre as colunas que a tabela já tem
            existing = {
                row[1]  # row = (cid, name, type, notnull, dflt, pk)
                for row in conn.execute(text(f"PRAGMA table_info({table})"))
            }
            for col_name, col_def in columns:
                if col_name not in existing:
                    conn.execute(
                        text(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_def}")
                    )


def ensure_seed_data() -> None:
    """
    Garante que as categorias padrão existem (cria se o banco estiver vazio).

    Chamado no startup do app. Diferente do script init_db (terminal),
    isto roda dentro do app — essencial para o .app empacotado, onde não
    há terminal para rodar o script de inicialização.

    Não cria usuário: a criação da conta é feita pela tela de cadastro
    na primeira abertura (ver needs_initial_setup).
    """
    from app.database.models import Category

    # Categorias padrão (mesma lista do script init_db)
    default_categories = [
        ("Food",          "#E85D24", "restaurant"),
        ("Transport",     "#1D9E75", "directions_car"),
        ("Leisure",       "#7F77DD", "sports_esports"),
        ("Groceries",     "#F2A623", "shopping_cart"),
        ("Health",        "#D4537E", "local_hospital"),
        ("Housing",       "#378ADD", "home"),
        ("Education",     "#534AB7", "school"),
        ("Other",         "#888780", "category"),
    ]

    from app.database.connection import get_session
    with get_session() as session:
        if session.query(Category).first() is None:
            for name, color, icon in default_categories:
                session.add(Category(name=name, color=color, icon=icon))
            session.commit()


def needs_initial_setup() -> bool:
    """
    True se ainda não há nenhum usuário — ou seja, é a primeira abertura
    e o app deve mostrar a tela de cadastro em vez do login.
    """
    from app.database.models import User
    from app.database.connection import get_session
    with get_session() as session:
        return session.query(User).first() is None
