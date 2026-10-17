import re
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

URL_RE = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
TRAILING = ".,;:!?)]}»"

# Encurtadores que precisam de uma requisição para revelar o destino.
SHORTENERS = {"vt.tiktok.com", "vm.tiktok.com", "t.co", "instagr.am", "bit.ly"}

TRACKING_PARAMS = {
    "fbclid", "gclid", "igshid", "igsh", "si", "feature", "ref", "ref_src",
    "s", "t", "_r", "_t", "srtk", "psln", "exln", "is_from_webview",
}

# Plataformas em que a identidade do conteúdo está toda no caminho.
PATH_ONLY = {"instagram", "tiktok", "x"}


def extract_urls(text: str) -> list[str]:
    seen: dict[str, None] = {}
    for m in URL_RE.finditer(text):
        seen.setdefault(m.group(0).rstrip(TRAILING), None)
    return list(seen)


def _host(url: str) -> str:
    host = (urlsplit(url).hostname or "").lower()
    return host.removeprefix("www.").removeprefix("m.")


def platform_of(url: str) -> str:
    host = _host(url)
    if host.endswith("instagram.com") or host == "instagr.am":
        return "instagram"
    if host.endswith("tiktok.com"):
        return "tiktok"
    if host in {"x.com", "twitter.com", "mobile.twitter.com", "fxtwitter.com", "vxtwitter.com"}:
        return "x"
    if host in {"youtube.com", "music.youtube.com", "youtu.be"}:
        return "youtube"
    return "web"


def needs_resolution(url: str) -> bool:
    return _host(url) in SHORTENERS


def canonicalize(url: str) -> str:
    """URL estável para deduplicação: sem rastreio, host normalizado, sem fragmento."""
    parts = urlsplit(url.strip())
    platform = platform_of(url)
    host = _host(url)
    path = parts.path

    if platform == "youtube":
        if host == "youtu.be":
            vid = path.strip("/")
        else:
            vid = (parse_qs(parts.query).get("v") or [""])[0]
            if not vid and path.startswith(("/shorts/", "/live/")):
                vid = path.split("/")[2]
        if vid:
            return f"https://www.youtube.com/watch?v={vid}"

    if platform == "x":
        host = "x.com"
    elif host == "instagr.am":
        host = "www.instagram.com"
    elif host in {"instagram.com", "tiktok.com"}:
        host = f"www.{host}"
    elif platform == "web":
        host = (parts.hostname or "").lower().removeprefix("www.")
        if parts.port:
            host += f":{parts.port}"

    path = re.sub(r"/{2,}", "/", path)
    if path != "/":
        path = path.rstrip("/")
    if platform == "instagram":
        path += "/"

    if platform in PATH_ONLY:
        query = ""
    else:
        kept = [
            (k, v)
            for k, v in sorted(parse_qs(parts.query, keep_blank_values=True).items())
            if not k.startswith("utm_") and k not in TRACKING_PARAMS
            for v in v
        ]
        query = urlencode(kept)

    return urlunsplit(("https", host, path, query, ""))


def resolve_redirects(url: str, timeout: float = 10.0) -> str:
    """Segue redirecionamentos de encurtadores. Retorna a URL original se falhar."""
    from curl_cffi import requests

    try:
        r = requests.get(url, impersonate="chrome", timeout=timeout, allow_redirects=True)
        return str(r.url)
    except Exception:
        return url
