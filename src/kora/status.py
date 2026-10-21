import time

import yt_dlp.version

from .agenda import Agenda, consultar, ler_execucao
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


def plural(n: int, singular: str, plural_: str) -> str:
    return f"{n} {singular if n == 1 else plural_}"


def linhas_worker(settings: Settings, agora: float, agenda: Agenda | None = None) -> list[str]:
    """Worker contínuo (batimento) ou em lotes (última e próxima execução)."""
    agenda = agenda or Agenda()
    try:
        delta = agora - settings.heartbeat_path.stat().st_mtime
    except OSError:
        delta = None
    if delta is not None and delta <= BATIMENTO_VIVO:
        return [f"• Modo: contínuo, ativo (batimento há {idade(delta)})"]

    ultima = ler_execucao(settings.execucao_path)
    if ultima:
        resultado = f"{plural(ultima['salvos'], 'salvo', 'salvos')}, {plural(ultima['falhas'], 'falha', 'falhas')}"
        linha_ultima = f"• Última execução: há {idade(agora - ultima['fim'])} ({resultado})"
    else:
        linha_ultima = "• Última execução: nenhuma registrada"

    if agenda.rodando:
        return ["• Lote rodando agora", linha_ultima]
    if not agenda.instalada:
        return [linha_ultima, "• Agendamento: não instalado (deploy/install.sh)"]
    if agenda.proxima is None:
        if agenda.defeito:
            return [linha_ultima, f"• ⚠️ Agendamento quebrado: {agenda.defeito}. Salve o intervalo em Ajustes "
                                  "ou rode deploy/install.sh"]
        return [linha_ultima, "• Próxima: indisponível"]
    if agenda.proxima > agora:
        return [linha_ultima, f"• Próxima: em {idade(agenda.proxima - agora)}"]
    return [linha_ultima, "• Próxima: vencida, aguardando disparo"]


def estado_ia(settings: Settings) -> str:
    try:
        provider = build_provider(settings)
    except ValueError as e:
        return f"configuração inválida ({e})"
    return provider.label if provider else "desligada"


def montar_status(queue: Queue, settings: Settings, agora: float | None = None,
                  agenda: Agenda | None = None) -> str:
    agora = time.time() if agora is None else agora
    c = queue.counts()
    linhas = [
        "Kora — status",
        "",
        "Lotes",
        *linhas_worker(settings, agora, agenda),
        "",
        "Fila",
        f"• Aguardando: {c.get(NA_FILA, 0)}",
        f"• Processando: {c.get(PROCESSANDO, 0)}",
        f"• Salvos: {c.get(CONCLUIDO, 0)}",
        f"• Falharam: {c.get(FALHOU, 0)}",
        f"• Notas pendentes de IA: {len(pendentes(settings))}",
        "",
        "Sistema",
        f"• IA: {estado_ia(settings)}",
        f"• yt-dlp: {yt_dlp.version.__version__}",
    ]
    if ultimo := queue.ultimo_concluido():
        item, quando = ultimo
        linhas += ["", "Último salvo", f"{item.titulo or item.url_canonica} (há {idade(agora - quando)})"]
    falhas = queue.falhas_recentes(5)
    if falhas:
        linhas += ["", "Falhas recentes"]
        for f in falhas:
            linhas += [f"• {f.url_canonica}", f"  {(f.erro or 'sem detalhe')[:160]}"]
    return "\n".join(linhas)


def texto_status(settings: Settings) -> str:
    """Abre a própria conexão: o SQLite não deixa uma conexão cruzar threads (o bot roda isto em to_thread)."""
    queue = Queue(settings.db_path)
    try:
        return montar_status(queue, settings, agenda=consultar())
    finally:
        queue.close()
