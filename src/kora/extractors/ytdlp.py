from pathlib import Path

import yt_dlp
from yt_dlp.networking.impersonate import ImpersonateTarget


def _date(upload_date: str | None) -> str:
    if upload_date and len(upload_date) == 8:
        return f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:]}"
    return ""


def _opts(**extra) -> dict:
    # `impersonate` é obrigatório para o TikTok (desafio anti-bot).
    return {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "noprogress": True,
        "impersonate": ImpersonateTarget("chrome"),
        **extra,
    }


def extract(url: str) -> dict:
    """Metadados, sem baixar mídia."""
    with yt_dlp.YoutubeDL(_opts(skip_download=True)) as ydl:
        info = ydl.extract_info(url, download=False)
    if info.get("_type") == "playlist" and info.get("entries"):
        info = next(e for e in info["entries"] if e)
    return {
        "titulo": info.get("title"),
        "autor": info.get("uploader") or info.get("channel") or "",
        "descricao": info.get("description") or "",
        "publicado": _date(info.get("upload_date")),
        "tem_midia": bool(info.get("formats")),
        "duracao": float(info.get("duration") or 0),
        "legendas": info.get("subtitles") or {},  # só as feitas por humanos
    }


def download_audio(url: str, directory: Path) -> Path:
    """Baixa só o áudio para `directory`; quem chama apaga a pasta depois."""
    # Sem faixa só de áudio (X), o menor vídeo basta.
    opts = _opts(format="bestaudio/worst", outtmpl=str(directory / "audio.%(ext)s"))
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([url])
    files = sorted(directory.glob("audio.*"))
    if not files:
        raise RuntimeError("yt-dlp não gerou arquivo de áudio")
    return files[0]
