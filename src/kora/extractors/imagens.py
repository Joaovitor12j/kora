"""URLs e download das imagens de posts de foto e carrosséis."""
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from . import fallback

EXTENSOES = {".jpg", ".jpeg", ".png", ".webp"}
MAX_BYTES = 12 * 1024 * 1024
PLATAFORMAS = {"instagram", "tiktok", "x"}


def so_imagens(linhas: list[str], maximo: int) -> list[str]:
    """Filtra a saída do `gallery-dl -g`: só URLs diretas de imagem, sem repetir."""
    urls: list[str] = []
    for linha in linhas:
        url = linha.strip()
        if not url.startswith("http") or url in urls:
            continue
        if Path(urlsplit(url).path).suffix.lower() in EXTENSOES:
            urls.append(url)
    return urls[:maximo]


def _gallery_dl(url: str, cookies: str, maximo: int) -> list[str]:
    cmd = [sys.executable, "-m", "gallery_dl", "-g", "--range", f"1-{maximo}"]
    if cookies:
        cmd += ["--cookies", cookies]
    r = subprocess.run([*cmd, url], capture_output=True, text=True, timeout=90)
    if r.returncode != 0 and not r.stdout.strip():
        raise RuntimeError((r.stderr.strip().splitlines() or ["gallery-dl falhou"])[-1][:150])
    return so_imagens(r.stdout.splitlines(), maximo)


def listar(url: str, plataforma: str, cookies: str = "", maximo: int = 10) -> list[str]:
    if plataforma == "x":
        return fallback.x_fotos(url)[:maximo]
    return _gallery_dl(url, cookies, maximo)


def baixar(urls: list[str], pasta: Path) -> list[Path]:
    """Baixa para `pasta`; imagem que falhar ou for grande demais é pulada."""
    arquivos: list[Path] = []
    with httpx.Client(timeout=30, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0"}) as client:
        for i, url in enumerate(urls, 1):
            try:
                r = client.get(url)
                r.raise_for_status()
            except httpx.HTTPError:
                continue
            if len(r.content) > MAX_BYTES:
                continue
            destino = pasta / f"{i:02d}{Path(urlsplit(url).path).suffix.lower() or '.jpg'}"
            destino.write_bytes(r.content)
            arquivos.append(destino)
    return arquivos
