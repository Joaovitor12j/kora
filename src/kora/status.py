import time

import yt_dlp.version

from .config import Settings
from .db import CONCLUIDO, FALHOU, NA_FILA, PROCESSANDO, Queue
from .llm import build_provider
from .reclassificar import pendentes

BATIMENTO_VIVO = 60.0  # o worker marca presença a cada 10 s


def idade(segundos: float) -> str:
    segundos = max(0, int(segundos))
    if segundos < 90:
        return f"{segundos} s"
    if segundos < 90 * 60:
        return f"{round(segundos / 60)} min"
    if segundos < 48 * 3600:
        return f"{round(segundos / 3600)} h"
    return f"{round(segundos / 86400)} d"


def estado_worker(settings: Settings, agora: float) -> str:
    try:
        ultimo = settings.heartbeat_path.stat().st_mtime
    except OSError:
        return "nunca iniciou (ou sem batimento ainda)"
    delta = agora - ultimo
    if delta <= BATIMENTO_VIVO:
        return f"ativo (batimento há {idade(delta)})"
    return f"PARADO (último batimento há {idade(delta)})"


def estado_ia(settings: Settings) -> str:
    try:
        provider = build_provider(settings)
    except ValueError as e:
        return f"configuração inválida ({e})"
    return provider.label if provider else "desligada"


def montar_status(queue: Queue, settings: Settings, agora: float | None = None) -> str:
    agora = time.time() if agora is None else agora
    c = queue.counts()
    linhas = [
        "Kora — status",
        f"worker: {estado_worker(settings, agora)}",
        f"fila: {c.get(NA_FILA, 0)} aguardando · {c.get(PROCESSANDO, 0)} processando · "
        f"{c.get(CONCLUIDO, 0)} salvos · {c.get(FALHOU, 0)} falharam",
        f"notas pendentes de IA: {len(pendentes(settings))}",
        f"IA: {estado_ia(settings)}",
        f"yt-dlp: {yt_dlp.version.__version__}",
    ]
    if ultimo := queue.ultimo_concluido():
        item, quando = ultimo
        linhas.append(f"último salvo: há {idade(agora - quando)} — {item.titulo or item.url_canonica}")
    falhas = queue.falhas_recentes(5)
    if falhas:
        linhas.append("falhas recentes:")
        linhas += [f"- {f.url_canonica}\n  {(f.erro or 'sem detalhe')[:160]}" for f in falhas]
    return "\n".join(linhas)


def texto_status(settings: Settings) -> str:
    """Abre a própria conexão: o SQLite não deixa uma conexão cruzar threads (o bot roda isto em to_thread)."""
    queue = Queue(settings.db_path)
    try:
        return montar_status(queue, settings)
    finally:
        queue.close()
