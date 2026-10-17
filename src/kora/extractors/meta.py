import re
from dataclasses import dataclass

from . import fallback, ytdlp


@dataclass
class Meta:
    url: str
    plataforma: str
    titulo: str
    autor: str = ""
    descricao: str = ""
    publicado: str = ""  # AAAA-MM-DD


def _titulo(raw: str | None, descricao: str, url: str) -> str:
    raw = (raw or "").strip()
    if raw and not re.match(r"^(Video|Photo|Post) by ", raw):
        return raw
    first = descricao.strip().splitlines()[0] if descricao.strip() else ""
    return (first[:80] or raw or url)


def fetch_meta(url: str, plataforma: str) -> Meta:
    """yt-dlp primeiro; fallback por plataforma quando ele não suporta o link."""
    try:
        info = ytdlp.extract(url)
    except Exception as first:
        try:
            info = fallback.extract(url, plataforma)
        except Exception as second:
            raise RuntimeError(f"yt-dlp: {first}; fallback: {second}") from second
    descricao = (info.get("descricao") or "").strip()
    return Meta(
        url=url,
        plataforma=plataforma,
        titulo=_titulo(info.get("titulo"), descricao, url),
        autor=info.get("autor") or "",
        descricao=descricao,
        publicado=info.get("publicado") or "",
    )


__all__ = ["Meta", "fetch_meta"]
