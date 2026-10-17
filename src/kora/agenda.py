"""Execução em lotes: registro da última rodada e consulta ao timer do systemd."""
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

TIMER = "kora-worker.timer"
SERVICO = "kora-worker.service"


def registrar_execucao(path: Path, inicio: float, fim: float, tentativas: int, salvos: int, falhas: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps({"inicio": inicio, "fim": fim, "tentativas": tentativas,
                               "salvos": salvos, "falhas": falhas}), encoding="utf-8")
    tmp.replace(path)  # troca atômica: o bot nunca lê um arquivo pela metade


def ler_execucao(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


@dataclass
class Agenda:
    instalada: bool = False  # o timer do systemd está ativo
    rodando: bool = False  # há um lote em andamento
    proxima: float | None = None  # epoch da próxima execução agendada


def _systemctl(*args: str) -> subprocess.CompletedProcess | None:
    try:
        return subprocess.run(["systemctl", "--user", *args], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return None


def _estado(unidade: str) -> str:
    r = _systemctl("is-active", unidade)
    return r.stdout.strip() if r else "indisponivel"


def parse_proxima(saida_json: str, unidade: str = TIMER) -> float | None:
    """`systemctl list-timers --output=json` -> epoch (s) da próxima execução do timer."""
    try:
        for linha in json.loads(saida_json):
            if linha.get("unit") == unidade and linha.get("next"):
                return linha["next"] / 1e6
    except (ValueError, TypeError, AttributeError):
        pass
    return None


def consultar() -> Agenda:
    instalada = _estado(TIMER) == "active"
    rodando = _estado(SERVICO) in ("activating", "active")
    proxima = None
    if instalada:
        r = _systemctl("list-timers", TIMER, "--output=json")
        proxima = parse_proxima(r.stdout) if r and r.returncode == 0 else None
    return Agenda(instalada, rodando, proxima)


def iniciar_lote() -> str:
    """'iniciado', 'andamento' (já rodando) ou 'indisponivel' (serviço não instalado)."""
    if _estado(SERVICO) in ("activating", "active"):
        return "andamento"
    r = _systemctl("start", "--no-block", SERVICO)
    return "iniciado" if r and r.returncode == 0 else "indisponivel"
