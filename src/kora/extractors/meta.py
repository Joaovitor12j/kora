import re
from dataclasses import dataclass, field

from . import article, fallback, ytdlp


@dataclass
class Meta:
    url: str
    plataforma: str
    titulo: str
    autor: str = ""
    descricao: str = ""
    publicado: str = ""  # AAAA-MM-DD
    conteudo: str = ""  # texto do artigo, legenda do site ou transcrição
    conteudo_tipo: str = ""  # artigo | legenda | transcricao
    tem_midia: bool = False
    duracao: float = 0.0
    legendas: dict = field(default_factory=dict)
    # Preenchidos pela IA (Fase 3); sem eles a nota fica com status pendente.
    resumo: str = ""
    pontos_chave: list[str] = field(default_factory=list)
    categoria: str = ""
    tags: list[str] = field(default_factory=list)
    ia: str = ""  # provedor/modelo que classificou
    criado: str = ""  # AAAA-MM-DD da nota original, preservado ao reprocessar


def _titulo(raw: str | None, descricao: str, url: str) -> str:
    raw = (raw or "").strip()
    if raw and not re.match(r"^(Video|Photo|Post) by ", raw):
        return raw
    first = descricao.strip().splitlines()[0] if descricao.strip() else ""
    return first[:80] or raw or url


def _fontes(plataforma: str):
    """Ordem de tentativa. Página comum: artigo primeiro; o yt-dlp genérico só se não houver texto."""
    if plataforma == "web":
        return [article.extract, ytdlp.extract, fallback.web]
    return [ytdlp.extract, lambda url: fallback.extract(url, plataforma)]


def _completar_x(url: str, info: dict) -> dict:
    """O yt-dlp corta tweets longos (~300 caracteres) e deixa t.co; o FixTweet traz o texto inteiro."""
    try:
        completo = fallback.x(url)
    except Exception:
        return info
    if len(completo["descricao"]) <= len(info.get("descricao") or ""):
        return info
    return {**info, "descricao": completo["descricao"], "titulo": completo["titulo"] or info.get("titulo")}


def fetch_meta(url: str, plataforma: str) -> Meta:
    erros = []
    for fonte in _fontes(plataforma):
        try:
            info = fonte(url)
            break
        except Exception as e:
            erros.append(str(e).splitlines()[0][:150] if str(e) else type(e).__name__)
    else:
        raise RuntimeError(" | ".join(erros))
    if plataforma == "x":
        info = _completar_x(url, info)
    descricao = (info.get("descricao") or "").strip()
    return Meta(
        url=url,
        plataforma=plataforma,
        titulo=_titulo(info.get("titulo"), descricao, url),
        autor=info.get("autor") or "",
        descricao=descricao,
        publicado=info.get("publicado") or "",
        conteudo=info.get("conteudo") or "",
        conteudo_tipo=info.get("conteudo_tipo") or "",
        tem_midia=info.get("tem_midia", False),
        duracao=info.get("duracao", 0.0),
        legendas=info.get("legendas") or {},
    )
