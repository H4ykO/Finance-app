"""
Categorizador automático de transações.

Quando uma transação chega (do CSV ou do e-mail), tentamos adivinhar
a categoria a partir de palavras-chave na descrição. Ex: "Uber" ->
Transporte, "EMPORIO DAMHA" -> Mercado.

POR QUE ISSO É ÚTIL?
Categorizar 360 transações na mão é inviável. Com regras de palavra-chave
acertamos a maioria automaticamente; o que sobrar fica como "Outros"
e o usuário ajusta na tela de Histórico.

COMO FUNCIONA?
Cada categoria tem uma lista de padrões (substrings em maiúsculo).
A descrição da transação é normalizada (maiúscula) e comparada.
A PRIMEIRA categoria cujo padrão casar vence — por isso a ordem
das regras importa (as mais específicas primeiro).

EVOLUÇÃO FUTURA POSSÍVEL:
Dá para trocar isso por um modelo de ML treinado nas suas próprias
correções. Mas regras simples cobrem ~80% dos casos sem complexidade.
"""

from dataclasses import dataclass


@dataclass
class CategoryRule:
    """Uma regra: se algum padrão casar, atribui esta categoria."""
    category_name: str
    patterns: list[str]


# Ordem importa: regras mais específicas devem vir ANTES das genéricas.
# Os padrões estão em MAIÚSCULAS porque comparamos com a descrição
# também em maiúsculas (case-insensitive na prática).
CATEGORY_RULES: list[CategoryRule] = [
    CategoryRule("Transport", [
        "UBER", "99POP", "99 POP", "UBERRIDES", "CABIFY", "POSTO",
        "GRAAL", "EXPRESSO ITAMARATI", "RODOSNACK", "ESTACIONAMENTO",
    ]),
    CategoryRule("Food", [
        "IFOOD", "IFD*", "RAPPI", "OUTBACK", "ESFIRRA", "ANDREA S FOOD",
        "FRANGO", "CASA DO FRANGO", "SORVETES", "GELATERIA", "CONFEITARI",
        "EMPORIO FACILITY", "MP *", "MP*", "ZAPPAS", "SJRP DAHMA",
        "JANGADA", "CAVATELLI", "BAIANO", "MAUA LTDA",
    ]),
    CategoryRule("Groceries", [
        "EMPORIO DAMHA", "PAO DE ACUCAR", "SUPERM", "MERCADO PAGUE POUCO",
        "ATACADAO", "CARREFOUR", "PORECATU",
    ]),
    CategoryRule("Health", [
        "DROGARIA", "DROGASIL", "RAIA", "FARMACIA", "EYE PHARMA",
        "LENTES PLUS", "PLURAL GEST EM P DE SAUDE",
    ]),
    CategoryRule("Leisure", [
        "SPOTIFY", "NETFLIX", "AMAZONPRIME", "AMAZON PRIME", "YOUTUBE",
        "PREMIUM", "RIOTGAME", "RIOT GAME", "NUUVEM", "PLAYSTATION",
        "STEAM", "ARENAHOT", "SHOP CENT IGUATEMI", "BORSATO BARBEARIA",
        "CLUBE LATAM",
    ]),
    CategoryRule("Education", [
        "ISCP", "SOCIEDADE EDUCACIONAL", "UDEMY", "KALUNGA", "EMPORIO CULTURAL",
    ]),
    CategoryRule("Housing", [
        "CLARO", "VIVO", "CPFL", "ENEL", "SABESP", "ULTRAGAZ", "IPTU",
        "LEROY MERLIN", "ASSOC. BRAS",
    ]),
    CategoryRule("Other", [
        "AMAZON", "MERCADOLIVRE", "MERCADO LIVRE", "ALIEXPRESS", "CENTAURO",
        "RIACHUELO", "HAVAIANAS", "LOJAS LIVIA", "CEABARUERI", "SAMSUNG",
        "NEW BRASIL", "PIX", "BOLETO", "FATURA", "PAGAMENTO", "SAQUE",
        "DEP DIN", "TED", "CXE", "RESGATE", "APLICACAO", "REND PAGO",
        "MENSALIDADE", "ANUIDADE", "DEP DISP",
    ]),
]


def guess_category_name(description: str) -> str:
    """
    Retorna o NOME da categoria adivinhada usando apenas as regras
    FIXAS do código (fallback).

    Se nada casar, retorna "Outros" como fallback seguro.
    """
    desc_upper = description.upper()

    for rule in CATEGORY_RULES:
        for pattern in rule.patterns:
            if pattern in desc_upper:
                return rule.category_name

    return "Other"


def guess_category_with_user_rules(
    description: str,
    user_rules: list[tuple[str, str]],
) -> str:
    """
    Adivinha a categoria consultando PRIMEIRO as regras do usuário,
    depois as regras fixas do código como fallback.

    `user_rules` é uma lista de (pattern_maiusculo, nome_categoria),
    já ordenada por especificidade (vinda de category_service).

    Por que as regras do usuário vêm primeiro? Porque elas são as
    correções/preferências explícitas dele — devem ter prioridade sobre
    os palpites genéricos do código.
    """
    desc_upper = description.upper()

    # 1. Regras do usuário (prioridade)
    for pattern, category_name in user_rules:
        if pattern in desc_upper:
            return category_name

    # 2. Fallback: regras fixas do código
    return guess_category_name(description)
