"""
Gerenciamento da sessão de autenticação rápida (PIN).

Regra de negócio: depois que o usuário faz login completo (e-mail + senha)
uma vez, ele pode reabrir o app usando apenas um PIN — até o computador
reiniciar. Quando o PC reinicia, o PIN "expira" e o login completo é
exigido de novo.

Como sabemos se o PC reiniciou? Comparando o horário do último boot do
sistema. Cada boot tem um horário único; se o horário gravado na última
autenticação for diferente do horário de boot atual, houve um reinício.

O estado é guardado num pequeno arquivo JSON na pasta de dados do app
(a mesma do banco), não no banco — assim é fácil de inspecionar e resetar.
"""

import json
import subprocess
import sys
from pathlib import Path

from app.config import settings


# Arquivo que guarda o estado da sessão (qual boot já foi autenticado).
_SESSION_FILE: Path = settings.DATA_DIR / "session.json"


def _system_boot_id() -> str:
    """
    Identificador do boot atual do sistema (muda a cada reinício).

    Usamos o horário do último boot como "id". Em macOS e Linux dá para
    obter sem dependências externas. Se algo falhar, caímos num valor
    fixo (o que torna a sessão sempre válida — fail-open para não travar
    o usuário fora do app; segurança aqui é conveniência, não barreira).
    """
    try:
        if sys.platform == "darwin":
            # macOS: sysctl retorna algo como "{ sec = 1700000000, usec = 0 }"
            out = subprocess.check_output(
                ["sysctl", "-n", "kern.boottime"], text=True, timeout=3
            )
            # Extrai o número após "sec ="
            for part in out.replace(",", " ").split():
                if part.isdigit():
                    return f"boot-{part}"
            return f"boot-raw-{out.strip()}"
        if sys.platform.startswith("linux"):
            # Linux: /proc/stat tem uma linha "btime <epoch>"
            with open("/proc/stat", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("btime"):
                        return f"boot-{line.split()[1]}"
            return "boot-linux-unknown"
        if sys.platform == "win32":
            # Windows: uptime via WMI seria o ideal; usamos um fallback simples.
            out = subprocess.check_output(
                ["powershell", "-NoProfile", "-Command",
                 "(Get-CimInstance Win32_OperatingSystem).LastBootUpTime"],
                text=True, timeout=5,
            )
            return f"boot-{out.strip()}"
    except Exception:
        pass
    # Fail-open: sem boot id confiável, devolve um marcador fixo
    return "boot-unknown"


def _read_state() -> dict:
    try:
        return json.loads(_SESSION_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_state(state: dict) -> None:
    try:
        _SESSION_FILE.write_text(json.dumps(state), encoding="utf-8")
    except Exception:
        # Se não der para gravar, o pior caso é pedir senha de novo — ok.
        pass


def mark_authenticated(user_id: int) -> None:
    """
    Registra que o usuário autenticou (login completo) nesta sessão de boot.

    Chamado após um login bem-sucedido com e-mail + senha. A partir daí,
    enquanto o PC não reiniciar, o app aceita o PIN.
    """
    _write_state({"user_id": user_id, "boot_id": _system_boot_id()})


def is_session_valid(user_id: int) -> bool:
    """
    True se este usuário já fez login completo na sessão de boot atual.

    Ou seja: o PC não reiniciou desde o último login completo. Nesse caso,
    o app pode pedir só o PIN em vez da senha.
    """
    state = _read_state()
    if state.get("user_id") != user_id:
        return False
    return state.get("boot_id") == _system_boot_id()


def clear_session() -> None:
    """
    Invalida a sessão (ex: logout explícito) — força login completo na
    próxima abertura.
    """
    try:
        _SESSION_FILE.unlink(missing_ok=True)
    except Exception:
        pass
