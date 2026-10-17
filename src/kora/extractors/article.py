import trafilatura
from curl_cffi import requests

MIN_CHARS = 200


def parse(page: str, url: str) -> dict:
    texto = trafilatura.extract(page, url=url, include_comments=False, include_tables=False) or ""
    if len(texto) < MIN_CHARS:
        raise ValueError("sem texto de artigo")
    meta = trafilatura.extract_metadata(page, default_url=url)
    return {
        "titulo": getattr(meta, "title", None),
        "autor": getattr(meta, "author", None) or getattr(meta, "sitename", None) or "",
        "descricao": getattr(meta, "description", None) or "",
        "publicado": (getattr(meta, "date", None) or "")[:10],
        "conteudo": texto,
        "conteudo_tipo": "artigo",
    }


def extract(url: str) -> dict:
    r = requests.get(url, impersonate="chrome", timeout=20, allow_redirects=True)
    r.raise_for_status()
    return parse(r.text, url)
