import logging
import time

from .config import Settings, get_settings
from .db import FALHOU, Item, Queue
from .extractors.meta import fetch_meta
from .telegram_api import send_message
from .vault import write_note

log = logging.getLogger("kora.worker")
IDLE_SLEEP = 2.0


def process(queue: Queue, settings: Settings, item: Item) -> str:
    """Extrai metadados e grava a nota. Retorna o título."""
    meta = fetch_meta(item.url_canonica, item.plataforma)
    path = write_note(settings.inbox_dir, meta, item.id)
    queue.done(item.id, meta.titulo, str(path))
    return meta.titulo


def notify(settings: Settings, item: Item, text: str) -> None:
    if not item.chat_id:
        return
    try:
        send_message(settings.telegram_bot_token, item.chat_id, text, item.message_id)
    except Exception:
        log.exception("falha ao avisar no Telegram (item %s)", item.id)


def run_once(queue: Queue, settings: Settings) -> bool:
    """Processa um item da fila. Retorna False se não havia nada a fazer."""
    item = queue.claim_next()
    if not item:
        return False
    log.info("processando #%s %s", item.id, item.url_canonica)
    try:
        titulo = process(queue, settings, item)
    except Exception as e:
        failed = queue.fail(item.id, str(e))
        log.warning("falha #%s (tentativa %s): %s", item.id, failed.tentativas, e)
        if failed.status == FALHOU:
            notify(settings, item, f"não consegui salvar: {item.url_canonica}\n{str(e)[:200]}")
    else:
        notify(settings, item, f"salvo: {titulo}")
    return True


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    settings = get_settings()
    queue = Queue(settings.db_path)
    log.info("retomando %s item(ns) interrompido(s)", queue.requeue_stuck())
    log.info("worker iniciado")
    try:
        while True:
            if not run_once(queue, settings):
                time.sleep(IDLE_SLEEP)
    except KeyboardInterrupt:
        log.info("worker encerrado")


if __name__ == "__main__":
    main()
