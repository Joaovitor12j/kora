import logging
import tempfile
from pathlib import Path

from .config import Settings
from . import ocr
from .extractors import article, imagens, legendas, ytdlp
from .extractors.meta import Meta
from .transcribe import transcribe
from .urls import extract_urls, platform_of

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


MIN_CHARS_OCR = 80  # abaixo disso o post é mais imagem que texto: a visão (se ligada) ajuda


def attach_imagens(meta: Meta, settings: Settings) -> None:
    """Posts de foto e carrosséis: lê o texto das imagens (OCR) e, se ligado, guarda JPEGs para a visão.

    Só age quando o post não tem vídeo nem texto de outra fonte. Falhas não derrubam o item.
    As imagens vivem numa pasta temporária que some ao fim.
    """
    if not settings.imagens_ler or meta.plataforma not in imagens.PLATAFORMAS:
        return
    if meta.tem_midia or meta.conteudo:
        return
    try:
        urls = imagens.listar(meta.url, meta.plataforma, settings.imagens_cookies, settings.imagens_max)
        if not urls:
            return
        with tempfile.TemporaryDirectory(prefix="kora-img-") as tmp:
            arquivos = imagens.baixar(urls, Path(tmp))
            blocos = [f"[slide {i}]\n{t}" for i, a in enumerate(arquivos, 1) if (t := ocr.ler(a))]
            texto = "\n\n".join(blocos)
            if texto:
                meta.conteudo, meta.conteudo_tipo = texto, "imagens"
            if settings.imagens_visao and len(texto) < MIN_CHARS_OCR:
                meta.imagens_visao = [ocr.reduzir(a) for a in arquivos[:4]]
    except Exception:
        log.warning("falha ao ler imagens de %s", meta.url, exc_info=True)


MAX_LINKS = 2  # tentativas por post


def attach_link(meta: Meta) -> None:
    """Post só com legenda curta que aponta para uma página: lê a página e usa o texto dela.

    Só age quando não há texto de outra fonte (transcrição, OCR, artigo). Falhas não derrubam o item.
    """
    if meta.conteudo or not meta.pobre:
        return
    candidatos = [u for u in extract_urls(meta.descricao) if platform_of(u) == "web" and u != meta.url]
    for url in candidatos[:MAX_LINKS]:
        try:
            info = article.extract(url)
        except Exception as e:
            log.info("link da legenda sem texto (%s): %s", url, str(e)[:100])
            continue
        meta.conteudo, meta.conteudo_tipo, meta.link_url = info["conteudo"], "link", url
        return
