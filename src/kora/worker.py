import argparse
import logging
import re
import threading
import time

from .config import Settings, get_settings
from .db import CONCLUIDO, FALHOU, Item, Queue
from .agenda import registrar_execucao
from .classificar import classificar
from .extractors.meta import Meta, fetch_meta
from .indice import garantir_indice
from .logs import configurar
from .llm import Provider, build_provider
from .media import attach_transcript
from .telegram_api import send_message
from .vault import destino, tags_existentes, write_note

log = logging.getLogger("kora.worker")
IDLE_SLEEP = 2.0
ESPERA_RETENTATIVA_MAX = 300.0  # no lote, espera o backoff de itens que falharam se for curto


def process(queue: Queue, settings: Settings, item: Item, provider: Provider | None = None) -> Meta:
    """Extrai, classifica e grava a nota. Sem IA, ela fica em _inbox com status pendente."""
    meta = fetch_meta(item.url_canonica, item.plataforma)
    attach_transcript(meta, settings)
    classificar(meta, provider, settings, tags_existentes(settings.saved_dir))
    path = write_note(destino(settings, meta), meta, item.id)
    queue.done(item.id, meta.titulo, str(path))
    return meta


def primeira_frase(texto: str, limite: int = 200) -> str:
    """Primeira frase do resumo; se for longa, corta numa palavra inteira."""
    frase = re.split(r"(?<=[.!?])\s", texto.strip().splitlines()[0], maxsplit=1)[0]
    if len(frase) <= limite:
        return frase
    return frase[:limite].rsplit(" ", 1)[0].rstrip(",;:") + "…"


def resposta(meta: Meta) -> str:
    if not meta.categoria:
        return f"salvo (sem IA): {meta.titulo}"
    return f"salvo em {meta.categoria}: {meta.titulo}\n{primeira_frase(meta.resumo)}"


def notify(settings: Settings, item: Item, text: str) -> int | None:
    """Avisa no Telegram e devolve o id da mensagem enviada (None se não deu)."""
    if not item.chat_id:
        return None
    try:
        return send_message(settings.telegram_bot_token, item.chat_id, text, item.message_id)
    except Exception:
        log.exception("falha ao avisar no Telegram (item %s)", item.id)
        return None


def run_once(queue: Queue, settings: Settings, provider: Provider | None = None) -> bool:
    """Processa um item da fila. Retorna False se não havia nada a fazer."""
    item = queue.claim_next()
    if not item:
        return False
    log.info("processando #%s %s", item.id, item.url_canonica)
    try:
        meta = process(queue, settings, item, provider)
    except Exception as e:
        failed = queue.fail(item.id, str(e))
        log.warning("falha #%s (tentativa %s): %s", item.id, failed.tentativas, e)
        if failed.status == FALHOU:
            notify(settings, item, f"não consegui salvar: {item.url_canonica}\n{str(e)[:200]}")
    else:
        queue.set_resposta(item.id, notify(settings, item, resposta(meta)))
    return True


def batimento(path, intervalo: float = 10.0) -> None:
    """Marca que o processo está vivo (o /status lê a idade do arquivo), mesmo durante uma transcrição longa."""
    while True:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch()
        except OSError:
            log.warning("não consegui atualizar %s", path)
        time.sleep(intervalo)


def executar_lote(queue: Queue, settings: Settings, provider: Provider | None,
                  dormir=time.sleep, agora=time.time) -> dict:
    """Esvazia a fila e retorna. Itens que falharam e voltam em poucos minutos (backoff) são esperados."""
    inicio, antes = agora(), queue.counts()
    tentativas = 0
    while True:
        if run_once(queue, settings, provider):
            tentativas += 1
            continue
        proxima = queue.proxima_tentativa(agora())
        if proxima is None or proxima - agora() > ESPERA_RETENTATIVA_MAX:
            break
        dormir(max(0.0, proxima - agora()) + 0.5)
    depois = queue.counts()
    resumo = {
        "tentativas": tentativas,
        "salvos": depois.get(CONCLUIDO, 0) - antes.get(CONCLUIDO, 0),
        "falhas": depois.get(FALHOU, 0) - antes.get(FALHOU, 0),
    }
    registrar_execucao(settings.execucao_path, inicio, agora(), **resumo)
    return resumo


def main() -> None:
    ap = argparse.ArgumentParser(description="Processa a fila de links do Kora.")
    ap.add_argument("--once", action="store_true",
                    help="esvazia a fila e sai (modo do timer do systemd); sem a flag, fica em loop")
    args = ap.parse_args()
    settings = get_settings()
    configurar(settings.log_level)
    queue = Queue(settings.db_path)
    provider = build_provider(settings)
    if garantir_indice(settings):
        log.info("índice Salvos.md criado")
    log.info("IA: %s", provider.label if provider else "desligada")
    log.info("retomando %s item(ns) interrompido(s)", queue.requeue_stuck())
    if args.once:
        settings.heartbeat_path.unlink(missing_ok=True)  # sobra do modo contínuo; lote não tem batimento
        log.info("lote iniciado: %s na fila", queue.counts().get("na_fila", 0))
        resumo = executar_lote(queue, settings, provider)
        log.info("lote concluído: %(salvos)s salvo(s), %(falhas)s falha(s), %(tentativas)s tentativa(s)", resumo)
        return
    threading.Thread(target=batimento, args=(settings.heartbeat_path,), daemon=True).start()
    log.info("worker contínuo iniciado")
    try:
        while True:
            if not run_once(queue, settings, provider):
                time.sleep(IDLE_SLEEP)
    except KeyboardInterrupt:
        log.info("worker encerrado")


if __name__ == "__main__":
    main()
