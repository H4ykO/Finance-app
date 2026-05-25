"""
Modelos do banco de dados.

Cada classe aqui vira UMA TABELA no SQLite.
Cada atributo Mapped[tipo] vira UMA COLUNA na tabela.

Modelo de dados do app:
- Tela de login                       -> tabela `users`
- Card "Available"                    -> tabela `available_balance`
- Card "Bills" (contas a pagar)       -> tabela `bills`
- Card "Income"                       -> tabela `incomes`
- Tabela "Last purchases" e gráficos  -> tabela `transactions`
- Pizza "Categories"                  -> tabela `categories` (FK em transactions)
"""

from __future__ import annotations  # permite usar "User" antes de declarado

from datetime import datetime, date
from decimal import Decimal
from typing import Optional

from sqlalchemy import String, ForeignKey, Numeric, Date, DateTime, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base


# ---------------------------------------------------------------------------
# Por que usar Numeric (Decimal) e não Float para dinheiro?
# ---------------------------------------------------------------------------
# Float em Python tem imprecisão binária: 0.1 + 0.2 = 0.30000000000000004.
# Para dinheiro isso é INACEITÁVEL — somar R$ 0,10 mil vezes daria erro.
# Numeric/Decimal guarda o valor exato como string internamente.
# Convenção: Numeric(12, 2) = até 10 dígitos antes da vírgula + 2 depois.
# ---------------------------------------------------------------------------


class User(Base):
    """Usuário do aplicativo. Inicialmente só existirá o admin."""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # unique=True garante que não existem dois usuários com mesmo e-mail
    # index=True cria um índice para acelerar buscas por e-mail (login)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)

    # Aqui guardamos o HASH da senha, NUNCA a senha em texto puro.
    # bcrypt gera hashes de ~60 caracteres, mas reservamos 255 por segurança.
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Hash do PIN de acesso rápido (opcional). Se definido, o usuário pode
    # reabrir o app com o PIN em vez da senha completa, até o PC reiniciar.
    pin_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Relacionamento: um usuário tem N transações
    # back_populates conecta com Transaction.user (do outro lado)
    transactions: Mapped[list["Transaction"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        # __repr__ ajuda no debug — print(user) fica legível
        return f"<User id={self.id} email={self.email!r}>"


class Category(Base):
    """Categoria de gasto: Alimentação, Transporte, Lazer, etc."""
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)

    # Cor em hex (ex: "#7F77DD") para mostrar no gráfico de pizza
    color: Mapped[str] = mapped_column(String(7), default="#888780", nullable=False)

    # Ícone (nome de ícone do Flet/Material, ex: "restaurant")
    icon: Mapped[str] = mapped_column(String(40), default="category", nullable=False)

    transactions: Mapped[list["Transaction"]] = relationship(back_populates="category")

    def __repr__(self) -> str:
        return f"<Category id={self.id} name={self.name!r}>"


class Transaction(Base):
    """
    Uma compra/gasto/recebimento.

    Cada linha da tabela "Last purchases" do dashboard vem daqui.
    Cada ponto do gráfico "Monthly Expenses" é uma soma destas linhas.
    """
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    user: Mapped["User"] = relationship(back_populates="transactions")

    # nullable=True porque uma transação pode chegar antes de categorizada
    category_id: Mapped[Optional[int]] = mapped_column(ForeignKey("categories.id"), nullable=True)
    category: Mapped[Optional["Category"]] = relationship(back_populates="transactions")

    # Descrição do estabelecimento (ex: "Uber", "iFood", "Posto Shell")
    description: Mapped[str] = mapped_column(String(255), nullable=False)

    # Valor SEMPRE positivo. O sinal vem do campo `kind`.
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    # "expense" (gasto), "income" (recebimento)
    # Usando String em vez de Enum por simplicidade e portabilidade
    kind: Mapped[str] = mapped_column(String(20), default="expense", nullable=False)

    # Data efetiva da transação (do extrato/notificação, não de quando foi inserida)
    occurred_at: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    # De onde veio: "manual", "email", "csv_import"
    # Útil para auditoria e para evitar processar a mesma compra duas vezes
    source: Mapped[str] = mapped_column(String(30), default="manual", nullable=False)

    # Identificador único da fonte original (ex: Message-ID do e-mail).
    # Usado para deduplicação: se já temos uma transação com este external_id,
    # não inserimos de novo. nullable porque transações manuais não têm.
    external_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, unique=True)

    # Espaço para observações livres do usuário
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<Transaction id={self.id} {self.description!r} R${self.amount}>"


class Bill(Base):
    """
    Conta a pagar (futura ou recorrente).

    Aparece no card "Bills" do dashboard.
    Diferente de Transaction: aqui é compromisso futuro,
    em Transaction é movimento que já aconteceu.
    """
    __tablename__ = "bills"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    description: Mapped[str] = mapped_column(String(255), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)

    is_paid: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    paid_at: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    # Se True, ao pagar esta conta o app gera automaticamente uma nova
    # instância para o mês seguinte (ex: assinaturas como Netflix/Spotify).
    is_recurring: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class Income(Base):
    """
    Renda mensal esperada/recebida.

    Aparece no card "Income". Tipicamente recorrente (salário),
    mas pode ser eventual (freelance, presente).
    """
    __tablename__ = "incomes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    description: Mapped[str] = mapped_column(String(255), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    received_at: Mapped[date] = mapped_column(Date, nullable=False)

    is_recurring: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class CategoryRule(Base):
    """
    Regra editável de categorização: "se a descrição contém X, é categoria Y".

    Diferente das regras fixas no código (categorizer.py), estas são
    criadas pelo usuário na tela de Categorias e ficam no banco. O
    categorizador consulta ESTAS primeiro; as do código são fallback.

    Ex: pattern="EMPORIO DAMHA" -> category "Mercado"
    """
    __tablename__ = "category_rules"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    # Texto a procurar na descrição (comparado em maiúsculas, "contém")
    pattern: Mapped[str] = mapped_column(String(120), nullable=False)

    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), nullable=False)
    category: Mapped["Category"] = relationship()

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<CategoryRule {self.pattern!r} -> cat={self.category_id}>"
