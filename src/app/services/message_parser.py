"""
Parser de linguagem natural para os lançamentos via Telegram.

Transforma mensagens livres como:
    "45,90 uber"                  -> gasto R$ 45,90, Uber, hoje, Transporte
    "120 conta de luz amanha"     -> gasto R$ 120, conta de luz, amanhã, Moradia
    "+3000 salario"               -> entrada R$ 3000, salário, hoje
    "recebi 500 freela ontem"     -> entrada R$ 500, freela, ontem
    "paguei 89,90 mercado 05/03"  -> gasto R$ 89,90, mercado, 05/03, Mercado

A filosofia: ser tolerante. O usuário escreve do jeito dele, e o parser
faz o melhor para extrair valor, descrição, data e tipo. O que não der
para inferir, usa padrões sensatos (data = hoje, tipo = gasto).

NÃO depende do Telegram nem do banco — recebe texto, devolve uma
estrutura. Isso o torna fácil de testar isoladamente.
"""

import re
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from typing import Optional

from app.services.categorizer import guess_category_with_user_rules


@dataclass
class ParsedMessage:
    """Resultado da interpretação de uma mensagem."""
    amount: Decimal
    description: str
    kind: str            # "expense" ou "income"
    occurred_at: date
    category_name: Optional[str]  # adivinhada; None para entradas


class ParseError(Exception):
    """Lançada quando não foi possível extrair o essencial (valor)."""
    pass


# Palavras que indicam ENTRADA (renda) em vez de gasto
_INCOME_KEYWORDS = [
    "recebi", "recebi", "salario", "salário", "entrada", "rendimento",
    "freela", "freelance", "pix recebido", "deposito", "depósito",
    "reembolso", "estorno", "vendi", "venda",
]

# Palavras de data relativa
_TODAY_WORDS = ["hoje"]
_YESTERDAY_WORDS = ["ontem"]
_TOMORROW_WORDS = ["amanha", "amanhã"]


def _extract_date(text: str, today: date) -> tuple[date, str]:
    """
    Procura uma data no texto. Retorna (data, texto_sem_a_data).

    Reconhece:
      - "hoje", "ontem", "amanhã"
      - "DD/MM" ou "DD/MM/AAAA"
    Se não achar nada, assume hoje.
    """
    lowered = text.lower()

    # Data explícita dd/mm ou dd/mm/aaaa
    m = re.search(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b", text)
    if m:
        day = int(m.group(1))
        month = int(m.group(2))
        year = today.year
        if m.group(3):
            year = int(m.group(3))
            if year < 100:  # "26" -> 2026
                year += 2000
        try:
            parsed = date(year, month, day)
            cleaned = (text[:m.start()] + text[m.end():]).strip()
            return parsed, cleaned
        except ValueError:
            pass  # data inválida (ex: 32/13) — ignora e segue

    # Datas relativas (palavras inteiras)
    for word in _YESTERDAY_WORDS:
        if word in lowered:
            return today - timedelta(days=1), _remove_word(text, word)
    for word in _TOMORROW_WORDS:
        if word in lowered:
            return today + timedelta(days=1), _remove_word(text, word)
    for word in _TODAY_WORDS:
        if word in lowered:
            return today, _remove_word(text, word)

    return today, text


def _remove_word(text: str, word: str) -> str:
    """Remove uma palavra do texto (case-insensitive), preservando o resto."""
    return re.sub(rf"\b{re.escape(word)}\b", "", text, flags=re.IGNORECASE).strip()


def _extract_amount(text: str) -> tuple[Decimal, str, bool]:
    """
    Extrai o valor monetário do texto.

    Retorna (valor, texto_sem_valor, tinha_sinal_de_mais).

    Reconhece formatos: "45,90", "45.90", "1.234,56", "1234", "+3000".
    O sinal de "+" é uma dica de que é entrada (income).

    A regex captura, em ordem de prioridade:
      - número com vírgula decimal e opcional milhar: 1.234,56 ou 45,90
      - número com ponto decimal (2 casas): 55.90
      - número inteiro com pontos de milhar: 1.234
      - inteiro simples: 120
    """
    # Detecta sinal de "+" colado ou separado por espaço antes do número
    plus_match = re.search(r"\+\s*\d", text)
    had_plus = plus_match is not None

    # Padrões testados na ordem (o primeiro que casar vence).
    # \b garante que pegamos o número inteiro, não um pedaço.
    patterns = [
        r"\d{1,3}(?:\.\d{3})+,\d{1,2}",   # 1.234,56 (milhar + decimal vírgula)
        r"\d+,\d{1,2}",                    # 45,90 (decimal vírgula)
        r"\d+\.\d{2}",                     # 55.90 (decimal ponto, 2 casas)
        r"\d{1,3}(?:\.\d{3})+",            # 1.234 (milhar com ponto, sem decimal)
        r"\d+",                            # 120 (inteiro)
    ]

    match = None
    for pat in patterns:
        match = re.search(pat, text)
        if match:
            break

    if not match:
        raise ParseError("Não encontrei um valor na mensagem.")

    raw = match.group(0)

    # Normaliza para Decimal
    if "," in raw:
        # Formato BR: ponto é milhar, vírgula é decimal
        normalized = raw.replace(".", "").replace(",", ".")
    elif re.match(r"^\d+\.\d{2}$", raw):
        # Decimal com ponto (ex: 55.90) — mantém
        normalized = raw
    else:
        # Pontos são milhar (ex: 1.234) — remove
        normalized = raw.replace(".", "")

    try:
        amount = Decimal(normalized)
    except InvalidOperation:
        raise ParseError(f"Valor inválido: {raw}")

    if amount <= 0:
        raise ParseError("O valor precisa ser maior que zero.")

    # Remove o trecho do valor (e um eventual "+" imediatamente antes) do texto
    start = match.start()
    # Recua para também remover um "+" colado/espaçado antes do número
    prefix = text[:start]
    prefix = re.sub(r"\+\s*$", "", prefix)
    cleaned = (prefix + text[match.end():]).strip()
    return amount, cleaned, had_plus


def parse_message(
    text: str,
    today: Optional[date] = None,
    user_rules: Optional[list[tuple[str, str]]] = None,
) -> ParsedMessage:
    """
    Interpreta uma mensagem de lançamento.

    Ordem do parsing:
      1. Extrai a data (e remove do texto)
      2. Extrai o valor (e remove do texto)
      3. O que sobra é a descrição
      4. Decide o tipo (entrada se tiver "+", "recebi", "salário"...)
      5. Adivinha a categoria (só para gastos)

    `today` é parametrizável para testes; em produção usa a data real.

    `user_rules` são as regras editáveis do usuário (pattern, categoria),
    que têm prioridade sobre as regras fixas do código. Se None, usa só
    as fixas. O bot passa as regras carregadas do banco aqui.
    """
    if today is None:
        today = date.today()

    original = text.strip()
    if not original:
        raise ParseError("Mensagem vazia.")

    # 1. Data
    occurred_at, text_no_date = _extract_date(original, today)

    # 2. Valor (precisa achar, senão erro)
    amount, text_no_amount, had_plus = _extract_amount(text_no_date)

    # 3. Descrição = o que sobrou, limpo
    description = re.sub(r"\s+", " ", text_no_amount).strip()
    # Remove palavras de comando/conectores que não fazem parte da descrição.
    # Inclui as palavras-chave de renda (recebi, salário...) pois elas indicam
    # o TIPO, não a descrição em si.
    _filler_words = [
        "paguei", "gastei", "comprei", "recebi", "ganhei",
        "de", "no", "na", "em", "do", "da",
    ]
    # Remove fillers no início, repetidamente (ex: "paguei de mercado")
    changed = True
    while changed:
        changed = False
        for filler in _filler_words:
            new_desc = re.sub(rf"^{filler}\b\s*", "", description, flags=re.IGNORECASE).strip()
            if new_desc != description:
                description = new_desc
                changed = True

    # 4. Tipo: entrada se teve "+" OU se há palavra-chave de renda
    lowered = original.lower()
    is_income = had_plus or any(kw in lowered for kw in _INCOME_KEYWORDS)
    kind = "income" if is_income else "expense"

    # Se não sobrou descrição, usa um rótulo genérico
    if not description:
        description = "Entrada" if is_income else "Gasto"

    # 5. Categoria (só para gastos; entradas ficam sem categoria)
    category_name = None
    if kind == "expense":
        # Usa as regras do usuário (prioridade) + fallback do código
        category_name = guess_category_with_user_rules(description, user_rules or [])

    return ParsedMessage(
        amount=amount,
        description=description,
        kind=kind,
        occurred_at=occurred_at,
        category_name=category_name,
    )
