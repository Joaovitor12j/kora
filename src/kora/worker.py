import logging
import re
import time

from .config import Settings, get_settings
from .db import FALHOU, Item, Queue
from .classificar import classificar
from .extractors.meta import Meta, fetch_meta
from .indice import garantir_indice
from .llm import Provider, build_provider
from .media import attach_transcript
from .telegram_api import send_message
from .vault import destino, tags_existentes, write_note

log = logging.getLogger("kora.worker")
IDLE_SLEEP = 2.0


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


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    settings = get_settings()
    queue = Queue(settings.db_path)
    provider = build_provider(settings)
    if garantir_indice(settings):
        log.info("índice Salvos.md criado")
    log.info("IA: %s", provider.label if provider else "desligada")
    log.info("retomando %s item(ns) interrompido(s)", queue.requeue_stuck())
    log.info("worker iniciado")
    try:
        while True:
            if not run_once(queue, settings, provider):
                time.sleep(IDLE_SLEEP)
    except KeyboardInterrupt:
        log.info("worker encerrado")


if __name__ == "__main__":
    main()
