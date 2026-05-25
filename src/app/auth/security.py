"""
Segurança: hash e verificação de senha.

POR QUE NÃO GUARDAR SENHA EM TEXTO PURO?
Se alguém ganhar acesso ao banco (vazamento, roubo do disco, etc.),
verá todas as senhas em texto puro. Como muita gente reusa senha,
o estrago vai além do app.

POR QUE BCRYPT E NÃO MD5 OU SHA256?
MD5/SHA256 são RÁPIDOS — atacantes conseguem testar bilhões de
combinações por segundo. Bcrypt é DELIBERADAMENTE lento (~250ms por
hash), o que torna ataques de força bruta inviáveis.

POR QUE BCRYPT DIRETO E NÃO PASSLIB?
A passlib foi o padrão por muitos anos, mas está mal mantida desde
2020 e quebra com versões recentes do bcrypt. A lib `bcrypt` tem API
simples, sem dependências extras, e está em desenvolvimento ativo.
"""

import bcrypt


# Limite técnico do bcrypt: senhas com mais de 72 bytes são truncadas.
# Documentamos a constante e validamos antes para evitar erros silenciosos.
_BCRYPT_MAX_BYTES = 72


def hash_password(plain_password: str) -> str:
    """
    Recebe a senha em texto puro e retorna o hash bcrypt como string.

    O hash já inclui o "salt" (valor aleatório) dentro dele, então
    duas senhas iguais geram hashes DIFERENTES — atacantes não
    conseguem identificar usuários com a mesma senha pelo hash.

    Estrutura do hash gerado:
        $2b$12$KIXxPp.NHK5RDhJh7TQH3.7eNcj...
        |   |  |                            |
        |   |  +-- salt (22 chars)          +-- hash final (31 chars)
        |   +-- "cost factor" (12 = ~250ms para gerar)
        +-- algoritmo (2b = bcrypt v2)
    """
    # bcrypt trabalha com BYTES, não strings. Encodamos em UTF-8.
    pwd_bytes = plain_password.encode("utf-8")

    # Validação explícita do limite de 72 bytes — evita comportamento
    # surpresa quando o usuário usa senha muito longa (emoji conta múltiplos bytes!)
    if len(pwd_bytes) > _BCRYPT_MAX_BYTES:
        raise ValueError(
            f"Senha tem {len(pwd_bytes)} bytes; limite do bcrypt é {_BCRYPT_MAX_BYTES}. "
            "Use uma senha mais curta."
        )

    # gensalt(rounds=12) -> cost factor 12. Padrão atual recomendado.
    # Cada incremento DOBRA o tempo de hash. 12 = ~250ms em CPU comum.
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(pwd_bytes, salt)

    # Voltamos para string porque é mais conveniente para guardar no banco
    return hashed.decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    """
    Compara uma senha em texto puro com um hash armazenado.

    Retorna True se a senha bate, False caso contrário.

    bcrypt.checkpw faz a comparação em TEMPO CONSTANTE para evitar
    "timing attacks" (atacante medindo o tempo de resposta para
    extrair informação sobre o hash).

    Se o hash estiver corrompido ou em formato inválido, retorna False
    em vez de lançar exceção — útil para o caminho de autenticação
    onde queremos sempre rejeitar e não vazar detalhes.
    """
    try:
        pwd_bytes = plain_password.encode("utf-8")
        hash_bytes = password_hash.encode("utf-8")

        # Senhas longas demais são inválidas por definição (não bateriam mesmo)
        if len(pwd_bytes) > _BCRYPT_MAX_BYTES:
            return False

        return bcrypt.checkpw(pwd_bytes, hash_bytes)
    except (ValueError, TypeError):
        # Hash mal-formatado: tratar como senha inválida silenciosamente
        return False
