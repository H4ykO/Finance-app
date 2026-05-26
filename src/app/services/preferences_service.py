"""
Preferências leves do app, persistidas em disco.

Guarda escolhas de interface que devem sobreviver ao fechar/reabrir o
app — como "ocultar valores de saldo". Usamos um pequeno arquivo JSON
na pasta de dados (a mesma do banco), em vez do banco, por simplicidade.
"""

import json
from pathlib import Path

from app.config import settings

_PREFS_FILE: Path = settings.DATA_DIR / "preferences.json"


def _read() -> dict:
    try:
        return json.loads(_PREFS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write(data: dict) -> None:
    try:
        _PREFS_FILE.write_text(json.dumps(data), encoding="utf-8")
    except Exception:
        # Se não der para gravar, a preferência só não persiste — sem drama.
        pass


def get_hide_balances() -> bool:
    """True se o usuário optou por ocultar os valores de saldo."""
    return bool(_read().get("hide_balances", False))


def set_hide_balances(value: bool) -> None:
    """Salva a preferência de ocultar/mostrar valores de saldo."""
    data = _read()
    data["hide_balances"] = bool(value)
    _write(data)
