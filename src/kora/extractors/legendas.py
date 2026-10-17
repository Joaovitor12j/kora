import re

from curl_cffi import requests

PREFERIDAS = ("pt", "en")
TAG = re.compile(r"<[^>]+>")


def escolher_url(legendas: dict) -> str | None:
    """Primeira legenda VTT, priorizando português e depois inglês."""
    idiomas = sorted(legendas, key=lambda lang: next(
        (i for i, p in enumerate(PREFERIDAS) if lang.lower().startswith(p)), len(PREFERIDAS)))
    for lang in idiomas:
        if not lang.lower().startswith(PREFERIDAS):
            continue
        for fmt in legendas[lang]:
            if fmt.get("ext") == "vtt" and fmt.get("url"):
                return fmt["url"]
    return None


def parse_vtt(vtt: str) -> str:
    linhas: list[str] = []
    for bloco in re.split(r"\n\s*\n", vtt.replace("\r\n", "\n")):
        partes = bloco.strip().splitlines()
        if not partes or partes[0].startswith(("WEBVTT", "NOTE", "STYLE", "REGION")):
            continue
        texto = [p for p in partes if "-->" not in p and not p.strip().isdigit()]
        linha = " ".join(TAG.sub("", t).strip() for t in texto).strip()
        if linha and (not linhas or linhas[-1] != linha):
            linhas.append(linha)
    return "\n".join(linhas)


def baixar(legendas: dict) -> str:
    url = escolher_url(legendas)
    if not url:
        return ""
    r = requests.get(url, impersonate="chrome", timeout=20)
    r.raise_for_status()
    return parse_vtt(r.text)
