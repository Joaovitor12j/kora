"""Reprocessa notas com status pendente (a IA estava fora do ar ou desligada).

Uso: uv run kora-reclassify [--limit N]
"""
import argparse
import logging
import re
from pathlib import Path

from .classificar import classificar
from .config import Settings, get_settings
from .db import Queue
from .llm import Provider, build_provider
from .vault import destino, ler_nota, tags_existentes, write_note

log = logging.getLogger("kora.reclassificar")
FALHAS_SEGUIDAS_MAX = 3  # provedor fora do ar: para em vez de esperar timeout em cada nota


def pendentes(settings: Settings) -> list[Path]:
    achadas = []
    for nota in sorted(settings.saved_dir.rglob("*.md")):
        try:
            cabecalho = nota.read_text(encoding="utf-8")[:2000]
        except OSError:
            continue
        if re.search(r"^status:\s*pendente\s*$", cabecalho, re.M) and "tipo: link" in cabecalho:
            achadas.append(nota)
    return achadas


def reclassificar(settings: Settings, queue: Queue, provider: Provider, limite: int | None = None) -> tuple[int, int]:
    """Devolve (reprocessadas, falhas)."""
    feitas = falhas = seguidas = 0
    for nota in pendentes(settings)[:limite]:
        meta, _ = ler_nota(nota)
        manual = meta.categoria  # categoria posta pelo usuário numa nota pendente vale mais que a da IA
        if not classificar(meta, provider, settings, tags_existentes(settings.saved_dir)):
            falhas += 1
            seguidas += 1
            log.warning("não reprocessada: %s", nota.name)
            if seguidas >= FALHAS_SEGUIDAS_MAX:
                log.error("%s falhas seguidas; parando", seguidas)
                break
            continue
        seguidas = 0
        meta.categoria = manual or meta.categoria
        item = queue.by_canonica(meta.url)
        novo = write_note(destino(settings, meta), meta, item.id if item else 0)
        if novo != nota:
            nota.unlink()
        if item:
            queue.set_nota(item.id, meta.titulo, str(novo))
        feitas += 1
        log.info("%s -> %s", nota.name, novo.relative_to(settings.saved_dir))
    return feitas, falhas


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, help="processa no máximo N notas")
    args = ap.parse_args()
    settings = get_settings()
    provider = build_provider(settings)
    if provider is None:
        raise SystemExit("Defina LLM_PROVIDER no .env (anthropic, deepseek ou ollama).")
    queue = Queue(settings.db_path)
    log.info("IA: %s; %s nota(s) pendente(s)", provider.label, len(pendentes(settings)))
    feitas, falhas = reclassificar(settings, queue, provider, args.limit)
    print(f"{feitas} reprocessada(s), {falhas} falha(s)")


if __name__ == "__main__":
    main()
