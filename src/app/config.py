"""
Configurações globais do aplicativo.

Este módulo é o ÚNICO lugar onde lemos variáveis de ambiente (.env).
Todos os outros módulos importam daqui, nunca leem `os.environ` direto.

Por quê? Centralização. Se amanhã trocarmos de python-dotenv para
outra biblioteca, ou movermos a configuração para um arquivo YAML,
só precisamos mudar este arquivo.

SOBRE O LOCAL DOS DADOS:
O app pode rodar de dois jeitos, e o banco precisa morar em lugares
diferentes em cada um:
  - DESENVOLVIMENTO (python main.py): dados em `data/` na pasta do
    projeto. Cômodo para desenvolver e inspecionar.
  - EMPACOTADO (.app no Mac): o Flet fornece um diretório próprio para
    dados persistentes, exposto na variável de ambiente
    FLET_APP_STORAGE_DATA (algo como
    ~/Library/Application Support/com.<org>.<app>/flet/data/).
    É lá que gravamos o banco e lemos o .env.
Detectamos o modo empacotado pela presença de FLET_APP_STORAGE_DATA
(definida pelo Flet em apps empacotados a partir da 0.25).
"""

import os
from pathlib import Path

from dotenv import load_dotenv


# O Flet define esta variável de ambiente em apps empacotados, apontando
# para o diretório de dados persistente do app. Em desenvolvimento
# (python main.py) ela normalmente não existe.
_FLET_DATA = os.getenv("FLET_APP_STORAGE_DATA")


def _is_packaged() -> bool:
    """True se rodando como app empacotado (flet build define FLET_APP_STORAGE_DATA)."""
    return bool(_FLET_DATA)


# Caminho raiz do projeto (a pasta finance_app/) — usado em desenvolvimento.
# Este arquivo está em src/app/config.py, então subimos três níveis:
#   config.py -> app/ -> src/ -> finance_app/ (raiz do projeto)
# É na raiz que ficam data/, .env e .venv.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Onde ficam os dados (banco, .env): depende do modo de execução.
if _is_packaged():
    # App empacotado: usa o diretório que o Flet fornece e gerencia.
    DATA_DIR = Path(_FLET_DATA)
else:
    # Desenvolvimento: data/ na raiz do projeto.
    DATA_DIR = BASE_DIR / "data"

# Garante que a pasta de dados existe antes de qualquer uso
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Carrega o .env. Em desenvolvimento, fica na raiz do projeto. No app
# empacotado, o usuário coloca o .env (com o token do Telegram) na pasta
# de dados do Flet (DATA_DIR), e nós o lemos de lá.
load_dotenv(BASE_DIR / ".env")
if _is_packaged():
    load_dotenv(DATA_DIR / ".env")


class Settings:
    """
    Container de configurações.

    Usamos uma classe (em vez de variáveis soltas no módulo) para:
    1. Agrupar configurações relacionadas
    2. Permitir validação no __init__ no futuro
    3. Facilitar mock em testes
    """

    # --- Banco de dados ---
    # O caminho do banco é SEMPRE calculado a partir de DATA_DIR (que já
    # é absoluto e correto para cada modo: dev usa data/ na raiz do
    # projeto; empacotado usa ~/Library/Application Support/).
    #
    # NÃO lemos DATABASE_URL do ambiente/.env de propósito: um caminho
    # relativo perdido lá (ex: "sqlite:///data/finance.db") quebraria o
    # app dependendo de onde ele é executado, e atrapalharia o .app
    # empacotado. O caminho calculado aqui é sempre o correto.
    DATABASE_URL: str = f"sqlite:///{DATA_DIR / 'finance.db'}"

    # --- Telegram Bot ---
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    # ID(s) de usuário do Telegram autorizado(s) a usar o bot.
    # Separados por vírgula se mais de um. Travamos por segurança para
    # que apenas você consiga registrar transações pelo bot.
    TELEGRAM_ALLOWED_USER_IDS: str = os.getenv("TELEGRAM_ALLOWED_USER_IDS", "")

    # --- Admin inicial ---
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "")

    # --- Diretórios ---
    BASE_DIR: Path = BASE_DIR
    DATA_DIR: Path = DATA_DIR
    IS_PACKAGED: bool = _is_packaged()


# Instância única (padrão singleton informal).
# Em todo o código fazemos: `from app.config import settings`
settings = Settings()
