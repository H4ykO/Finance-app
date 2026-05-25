"""
Importador de CSV de extrato/fatura bancária.

Formato suportado (Itaú, conforme arquivo de exemplo):
    date,title,amount
    2026-03-04,Pagamento de boleto,100.0
    2026-03-03,CXE TEF 0045.45975-7,-1000.0

CONVENÇÃO DE SINAL DESTE BANCO (importante!):
  - amount POSITIVO  -> GASTO / saída de dinheiro (compra, boleto, mensalidade)
  - amount NEGATIVO  -> ENTRADA / crédito (pagamento, resgate, estorno, recebimento)

Isso é o INVERSO da intuição comum, então convertemos para o nosso
modelo interno onde guardamos sempre:
  - amount POSITIVO (valor absoluto)
  - kind = "expense" para gastos, "income" para entradas

DEDUPLICAÇÃO:
Geramos um `external_id` determinístico (hash de data+título+valor).
Se reimportar o mesmo arquivo, as transações repetidas são ignoradas
pelo banco (coluna external_id é unique). Isso permite importar o
extrato do mês várias vezes sem duplicar.
"""

import csv
import hashlib
import io
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import Category, Transaction
from app.services.categorizer import guess_category_with_user_rules
from app.services.category_service import get_user_rules_map


# ---------------------------------------------------------------------------
# Resultado da importação — para mostrar um resumo ao usuário
# ---------------------------------------------------------------------------
@dataclass
class ImportResult:
    """Resumo do que aconteceu na importação."""
    total_rows: int = 0            # linhas lidas do arquivo
    imported: int = 0              # novas transações gravadas
    duplicates: int = 0            # ignoradas por já existirem
    errors: list[str] = field(default_factory=list)  # linhas com problema

    def summary(self) -> str:
        """Texto amigável para mostrar na UI."""
        parts = [
            f"{self.imported} importadas",
            f"{self.duplicates} duplicadas (ignoradas)",
        ]
        if self.errors:
            parts.append(f"{len(self.errors)} com erro")
        return ", ".join(parts)


# ---------------------------------------------------------------------------
# Geração do external_id (deduplicação)
# ---------------------------------------------------------------------------
def _make_external_id(date_str: str, title: str, amount_str: str) -> str:
    """
    Cria um identificador determinístico a partir dos campos da linha.

    Usamos SHA-256 truncado. Como é determinístico, a MESMA linha sempre
    gera o MESMO id — então reimportar não duplica.

    Prefixo "csv:" deixa claro de onde veio (útil para depuração e para
    não colidir com ids de e-mail no futuro, que terão prefixo "email:").
    """
    raw = f"{date_str}|{title}|{amount_str}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"csv:{digest}"


# ---------------------------------------------------------------------------
# Parse de uma linha
# ---------------------------------------------------------------------------
@dataclass
class ParsedRow:
    """Uma linha do CSV já interpretada para o nosso modelo."""
    occurred_at: datetime
    description: str
    amount: Decimal      # sempre positivo
    kind: str            # "expense" ou "income"
    external_id: str


def _parse_row(row: dict) -> ParsedRow:
    """
    Converte uma linha bruta do CSV em ParsedRow.

    Lança ValueError se a linha estiver malformada (data/valor inválido).
    """
    date_str = (row.get("date") or "").strip()
    title = (row.get("title") or "").strip()
    amount_str = (row.get("amount") or "").strip()

    if not date_str or not title or not amount_str:
        raise ValueError("linha incompleta (faltam campos)")

    # Data: formato ISO yyyy-mm-dd
    try:
        occurred_at = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        raise ValueError(f"data inválida: {date_str!r}")

    # Valor: aceita ponto decimal; converte para Decimal preservando precisão
    try:
        raw_amount = Decimal(amount_str)
    except (InvalidOperation, ValueError):
        raise ValueError(f"valor inválido: {amount_str!r}")

    # Aplica a convenção de sinal do banco:
    #   positivo -> expense ; negativo -> income
    if raw_amount >= 0:
        kind = "expense"
        amount = raw_amount
    else:
        kind = "income"
        amount = -raw_amount  # torna positivo

    external_id = _make_external_id(date_str, title, amount_str)

    return ParsedRow(
        occurred_at=occurred_at,
        description=title,
        amount=amount,
        kind=kind,
        external_id=external_id,
    )


# ---------------------------------------------------------------------------
# Importação principal
# ---------------------------------------------------------------------------
def import_csv_text(
    session: Session,
    user_id: int,
    csv_text: str,
) -> ImportResult:
    """
    Importa transações a partir do CONTEÚDO de um CSV (string).

    Recebe texto (não caminho) para ser testável e desacoplado de
    sistema de arquivos. A view lê o arquivo e passa o texto.

    Estratégia de deduplicação em DUAS camadas:
      1. Dentro do próprio arquivo (um set de ids já vistos nesta importação)
      2. Contra o banco (busca external_ids já existentes de uma vez)
    """
    result = ImportResult()

    # csv.DictReader usa a primeira linha como cabeçalho
    reader = csv.DictReader(io.StringIO(csv_text))

    # Validação do cabeçalho — falha cedo com mensagem clara
    expected = {"date", "title", "amount"}
    if reader.fieldnames is None or not expected.issubset(set(reader.fieldnames)):
        result.errors.append(
            f"Cabeçalho inválido. Esperado: {sorted(expected)}, "
            f"encontrado: {reader.fieldnames}"
        )
        return result

    # Parse de todas as linhas primeiro (separando válidas de inválidas)
    parsed_rows: list[ParsedRow] = []
    for i, row in enumerate(reader, start=2):  # start=2: linha 1 é cabeçalho
        result.total_rows += 1
        try:
            parsed_rows.append(_parse_row(row))
        except ValueError as e:
            result.errors.append(f"linha {i}: {e}")

    if not parsed_rows:
        return result

    # --- Deduplicação contra o banco ---
    # Busca de uma só vez todos os external_ids deste lote que JÁ existem
    incoming_ids = {p.external_id for p in parsed_rows}
    existing_ids = set(
        session.scalars(
            select(Transaction.external_id).where(
                Transaction.user_id == user_id,
                Transaction.external_id.in_(incoming_ids),
            )
        ).all()
    )

    # --- Mapa de categorias (nome -> id) para categorização ---
    categories = session.query(Category).all()
    cat_id_by_name = {c.name: c.id for c in categories}

    # --- Regras de categorização do usuário (têm prioridade) ---
    user_rules = get_user_rules_map(session, user_id)

    # --- Inserção ---
    seen_in_file: set[str] = set()
    new_transactions: list[Transaction] = []

    for p in parsed_rows:
        # Duplicada dentro do próprio arquivo?
        if p.external_id in seen_in_file:
            result.duplicates += 1
            continue
        seen_in_file.add(p.external_id)

        # Já existe no banco?
        if p.external_id in existing_ids:
            result.duplicates += 1
            continue

        # Categorização automática (só para despesas; entradas ficam sem categoria)
        category_id: Optional[int] = None
        if p.kind == "expense":
            cat_name = guess_category_with_user_rules(p.description, user_rules)
            category_id = cat_id_by_name.get(cat_name)

        new_transactions.append(
            Transaction(
                user_id=user_id,
                category_id=category_id,
                description=p.description,
                amount=p.amount,
                kind=p.kind,
                occurred_at=p.occurred_at,
                source="csv_import",
                external_id=p.external_id,
            )
        )
        result.imported += 1

    # Grava tudo de uma vez (mais eficiente que commit por linha)
    if new_transactions:
        session.add_all(new_transactions)
        session.commit()

    return result
