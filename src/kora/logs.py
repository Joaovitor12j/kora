import logging
import os

# Bibliotecas HTTP logam a URL de cada requisição; a do Telegram leva o token do bot.
RUIDOSAS = ("httpx", "httpx2", "httpcore", "httpcore2", "hpack")


def configurar(nivel: str = "INFO") -> None:
    # Sob o systemd o journal já carimba a hora; em terminal, o log precisa dela.
    formato = "%(levelname)s %(name)s %(message)s" if os.environ.get("JOURNAL_STREAM") \
        else "%(asctime)s %(levelname)s %(name)s %(message)s"
    logging.basicConfig(level=nivel.upper(), format=formato)
    for nome in RUIDOSAS:
        logging.getLogger(nome).setLevel(logging.WARNING)
