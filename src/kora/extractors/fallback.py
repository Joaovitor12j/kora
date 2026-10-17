"""Metadados de links que o yt-dlp não suporta (post de foto do Instagram, artigos, TikTok)."""
import html
import re

from curl_cffi import requests

OG_RE = r'<meta[^>]+property="og:%s"[^>]+content="([^"]*)"'


def og(page: str, key: str) -> str:
    m = re.search(OG_RE % key, page)
    return html.unescape(m.group(1)).strip() if m else ""


def parse_instagram(og_title: str, og_description: str) -> tuple[str, str]:
    """`Fulano on Instagram: "legenda"` -> (autor, legenda)."""
    autor = og_title.split(" on Instagram", 1)[0].strip() if " on Instagram" in og_title else ""
    for source in (og_title, og_description):
        m = re.search(r':\s*"(.*)"\s*\.?\s*$', source, re.S)
        if m:
            return autor, m.group(1).strip()
    return autor, ""


def _get(url: str, **kw):
    r = requests.get(url, timeout=20, allow_redirects=True, **kw)
    r.raise_for_status()
    return r


def instagram(url: str) -> dict:
    # O Instagram só entrega og:tags completas para o scraper do Facebook.
    page = _get(url, headers={"User-Agent": "facebookexternalhit/1.1"}).text
    autor, legenda = parse_instagram(og(page, "title"), og(page, "description"))
    if not (autor or legenda):
        raise ValueError("sem og:tags no post do Instagram")
    return {"titulo": None, "autor": autor, "descricao": legenda}


def tiktok(url: str) -> dict:
    data = _get("https://www.tiktok.com/oembed", params={"url": url}, impersonate="chrome").json()
    return {"titulo": None, "autor": data.get("author_name", ""), "descricao": data.get("title", "")}


def web(url: str) -> dict:
    page = _get(url, impersonate="chrome").text
    titulo = og(page, "title")
    if not titulo:
        m = re.search(r"<title[^>]*>(.*?)</title>", page, re.S | re.I)
        titulo = html.unescape(m.group(1)).strip() if m else ""
    if not titulo:
        raise ValueError("página sem título")
    return {"titulo": titulo, "autor": og(page, "site_name"), "descricao": og(page, "description")}


def extract(url: str, plataforma: str) -> dict:
    handler = {"instagram": instagram, "tiktok": tiktok, "web": web}.get(plataforma)
    if not handler:
        raise ValueError(f"sem fallback para {plataforma}")
    return handler(url)
