import logging
import tempfile
from pathlib import Path

from .config import Settings
from .extractors import legendas, ytdlp
from .extractors.meta import Meta
from .transcribe import transcribe

log = logging.getLogger("kora.media")


def attach_transcript(meta: Meta, settings: Settings) -> None:
    """Preenche `meta.conteudo` com a legenda do site ou, na falta, a transcrição do áudio.

    Falhas aqui não derrubam o item: a nota sai com os metadados e a legenda original.
    """
    if not meta.tem_midia or meta.conteudo:
        return
    if meta.duracao > settings.max_audio_minutes * 60:
        log.info("vídeo de %.0f min acima do limite; sem transcrição", meta.duracao / 60)
        return
    try:
        if texto := legendas.baixar(meta.legendas):
            meta.conteudo, meta.conteudo_tipo = texto, "legenda"
            return
    except Exception:
        log.warning("legenda do site indisponível, transcrevendo o áudio", exc_info=True)
    try:
        with tempfile.TemporaryDirectory(prefix="kora-") as tmp:  # o áudio some junto com a pasta
            audio = ytdlp.download_audio(meta.url, Path(tmp))
            meta.conteudo = transcribe(audio, settings.whisper_model, settings.whisper_language)
            meta.conteudo_tipo = "transcricao"
    except Exception:
        log.warning("falha ao transcrever %s", meta.url, exc_info=True)
