import yt_dlp
from yt_dlp.networking.impersonate import ImpersonateTarget


def _date(upload_date: str | None) -> str:
    if upload_date and len(upload_date) == 8:
        return f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:]}"
    return ""


def extract(url: str) -> dict:
    """Só metadados. `impersonate` é obrigatório para o TikTok (desafio anti-bot)."""
    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
        "impersonate": ImpersonateTarget("chrome"),
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
    if info.get("_type") == "playlist" and info.get("entries"):
        info = next(e for e in info["entries"] if e)
    return {
        "titulo": info.get("title"),
        "autor": info.get("uploader") or info.get("channel") or "",
        "descricao": info.get("description") or "",
        "publicado": _date(info.get("upload_date")),
    }
